"""Dockable, asynchronous Search / Results / Workspace interface."""

import json
from pathlib import Path
from urllib.parse import quote, urljoin

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsAuthMethodConfig,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsMessageLog,
    QgsProject,
    QgsProviderRegistry,
    QgsRasterLayer,
    QgsTask,
    QgsVectorLayer,
)
from qgis.PyQt import QtCore, QtGui, QtWidgets

from eodh_qgis.api.hub import (
    ENVIRONMENTS,
    HubClient,
    HubError,
    asset_type,
    href,
    link,
    record_status,
    search_body,
    validate_bbox,
)
from eodh_qgis.api.presentation import bbox2d, overlap, parsed_date, quick_view, thumbnail_asset

from .hub_cards import CardList, ResultCard, Timeline, WorkspaceCard, busy_bar, hyperlink, text_label
from .hub_login import LoginPage
from .hub_map import WGS84, Overlays, RectangleTool, geometry
from .hub_scroll import ScrollComboBox, SmoothScrollArea
from .hub_widgets import button, label


class HubTask(QgsTask):
    download_progress = QtCore.pyqtSignal(str, object, object)
    asset_stage = QtCore.pyqtSignal(str)
    thumbnail_ready = QtCore.pyqtSignal(int, object)

    def __init__(self, title, work, finish):
        super().__init__(title, QgsTask.Flag.CanCancel | QgsTask.Flag.Silent)
        self.work, self.finish_callback = work, finish
        self.result, self.error = None, None

    def run(self):
        try:
            if self.work is None or self.isCanceled():
                return False
            self.result = self.work()
            return True
        except Exception as error:
            self.error = error
            return False

    def finished(self, success):
        if self.finish_callback is not None:
            error = HubError("Operation cancelled.") if self.isCanceled() else self.error
            self.finish_callback(self.result, error)
        self.work = self.finish_callback = None


class HubDock(QtWidgets.QDockWidget):
    def __init__(self, iface, parent=None):
        super().__init__("EO Data Hub", parent or iface.mainWindow())
        self.setObjectName("EodhHubDock")
        self.iface, self.client = iface, None
        self.epoch, self.discovery_id, self.search_id, self.selection_id = 0, 0, 0, 0
        self.tasks, self.items, self.records = [], [], []
        self.result_cards, self.record_cards, self.pages = [], [], []
        self.page_index, self.workspace_generation = 0, 0
        self.aoi_from_collection = False
        self.bbox, self.next_link, self.search_params = None, None, None
        self.overlays = Overlays(iface.mapCanvas())
        self.draw_tool = RectangleTool(iface.mapCanvas())
        self.draw_tool.captured.connect(self.drawn)
        self.previous_tool = None
        self.root = QtWidgets.QWidget()
        self.root.setMinimumWidth(370)
        self.setWidget(self.root)
        layout = QtWidgets.QVBoxLayout(self.root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.header = QtWidgets.QWidget()
        header = QtWidgets.QHBoxLayout(self.header)
        self.header.setObjectName("brandHeader")
        header.setContentsMargins(9, 7, 7, 6)
        header.setSpacing(9)
        mark = QtWidgets.QLabel()
        mark.setPixmap(
            QtGui.QPixmap(str(Path(__file__).parents[1] / "brand" / "eodh-mark.png")).scaled(
                35, 35, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation
            )
        )
        header.addWidget(mark)
        account = QtWidgets.QVBoxLayout()
        account.setSpacing(0)
        self.workspace_label = text_label("", 12, True)
        account.addWidget(self.workspace_label)
        account.addWidget(text_label("•  production", 10, color="#666"))
        header.addLayout(account, 1)
        switch = button("Switch", self.disconnect)
        switch.setToolTip("Switch workspace")
        switch.setObjectName("headerAction")
        header.addWidget(switch)
        separator = QtWidgets.QFrame()
        separator.setFixedSize(1, 18)
        separator.setStyleSheet("background:rgba(76,114,186,56);")
        header.addWidget(separator)
        self.sign_out = button("Log out", self.disconnect)
        self.sign_out.setObjectName("headerAction")
        header.addWidget(self.sign_out)
        self.header.hide()
        layout.addWidget(self.header)
        self.stack = QtWidgets.QStackedWidget()
        layout.addWidget(self.stack, 1)
        self.footer = QtWidgets.QWidget()
        self.footer.setObjectName("activityFooter")
        self.footer.setFixedHeight(56)
        activity = QtWidgets.QGridLayout(self.footer)
        activity.setContentsMargins(8, 5, 8, 5)
        activity.setSpacing(2)
        badge = text_label("STATUS", 8, True, "#666")
        badge.setStyleSheet(badge.styleSheet() + "background:rgba(128,128,128,36);border-radius:2px;padding:1px 5px;")
        activity.addWidget(badge, 0, 0)
        self.status = text_label("Ready", 10, True)
        self.status.setAccessibleName("EODH status")
        self.status.hide()
        activity.addWidget(self.status, 0, 1)
        self.status_detail = text_label("", 9, color="#666")
        activity.addWidget(self.status_detail, 1, 1, 1, 2)
        self.status_percent = text_label("", 10, True)
        activity.addWidget(self.status_percent, 0, 2)
        activity.setColumnStretch(1, 1)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(3)
        self.progress.hide()
        activity.addWidget(self.progress, 2, 0, 1, 3)
        layout.addWidget(self.footer)
        self.footer.hide()
        self.root.setStyleSheet(
            'QWidget {font-family:"Segoe UI";font-size:12px;color:#222;} '
            "QWidget#brandHeader {background:rgba(76,114,186,16);border-bottom:2px solid #4c72ba;} "
            "QWidget#activityFooter {background:rgba(128,128,128,28);border-top:1px solid #aaa;} "
            "QPushButton {border:1px solid #888;border-radius:0;background:#dedede;padding:3px 7px;} "
            "QPushButton:hover {background:#e5f1fb;border-color:#0078d7;} "
            "QPushButton:disabled {color:#999;background:#eee;border-color:#ccc;} "
            "QPushButton#headerAction {background:transparent;border:0;color:#4c72ba;font-size:11px;padding:4px 6px;} "
            "QPushButton#headerAction:hover {background:rgba(76,114,186,24);} "
            "QPushButton#assetLink {background:transparent;border:0;color:#3070c0;text-decoration:underline;padding:0;font-size:10px;} "
            "QLineEdit,QComboBox,QDateEdit {min-height:20px;border:1px solid #aaa;background:white;padding:0 3px;} "
            "QTabWidget::pane {border:1px solid #ccc;background:#f8f8f8;} "
            "QTabBar::tab {background:#eee;border:1px solid #ccc;padding:2px 7px;} "
            "QTabBar::tab:selected {background:#f8f8f8;border-bottom-color:#f8f8f8;} "
            "QProgressBar {border:0;background:#ddd;} QProgressBar::chunk {background:#4c72ba;}"
        )
        self.build_login()
        self.tabs = QtWidgets.QTabWidget()
        self.stack.addWidget(self.tabs)
        self.build_search()
        self.build_results()
        self.build_workspace()
        self.visibilityChanged.connect(self.visibility_changed)
        self.iface.mapCanvas().destinationCrsChanged.connect(self.update_overlays)
        if self.auth_id and QtCore.QSettings().value("eodh/hub_environment", "Production") == "Production":
            QtCore.QTimer.singleShot(0, self.load_credentials)

    def page(self, title):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        scroll = SmoothScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        self.tabs.addTab(scroll, title)
        return page, layout

    def build_login(self):
        self.login = LoginPage(self.connect_workspace)
        self.workspace, self.key = self.login.workspace, self.login.key
        self.connect_button = self.login.connect_button
        self.login_scroll = SmoothScrollArea()
        self.login_scroll.setWidgetResizable(True)
        self.login_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.login_scroll.setWidget(self.login)
        self.stack.addWidget(self.login_scroll)
        settings = QtCore.QSettings()
        self.workspace.setText(settings.value("eodh/hub_workspace", ""))
        self.auth_id = settings.value("eodh/hub_auth", "")

    def load_credentials(self):
        if not self.auth_id or self.client or self.login.loading:
            return
        config = QgsAuthMethodConfig()
        if QgsApplication.authManager().loadAuthenticationConfig(self.auth_id, config, True):
            self.key.setText(config.config("token"))
            self.connect_workspace(saved=True)

    def connect_workspace(self, checked=False, *, saved=False):
        if self.login.loading:
            return
        workspace, key = self.workspace.text().strip(), self.key.text().strip()
        if not workspace:
            return
        if not key:
            self.login.set_error("Please enter your workspace API key (not the Token ID).")
            return
        client = HubClient(ENVIRONMENTS["Production"], workspace, key)
        self.login.set_error("")
        self.login.set_loading(True)

        def done(result):
            self.client = client
            from eodh_qgis.raster_loader import reconnect_streams

            reconnect_streams(client, QgsProject.instance().mapLayers().values())
            self.login.set_loading(False)
            if not saved:
                config = QgsAuthMethodConfig()
                config.setName("EODH workspace")
                config.setMethod("APIHeader")
                config.setConfig("token", key)
                config.setConfig("Authorization", "Bearer " + key)
                manager = QgsApplication.authManager()
                if self.auth_id:
                    config.setId(self.auth_id)
                    stored = manager.updateAuthenticationConfig(config)
                else:
                    stored = manager.storeAuthenticationConfig(config)
                if stored:
                    self.auth_id = config.id()
                    QtCore.QSettings().setValue("eodh/hub_auth", self.auth_id)
                else:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "EODH",
                        "Connected, but QGIS could not save your credentials. Unlock or configure the QGIS "
                        "authentication database to remember them next time.",
                    )
            settings = QtCore.QSettings()
            settings.setValue("eodh/hub_workspace", workspace)
            settings.setValue("eodh/hub_environment", "Production")
            self.key.clear()
            self.workspace_label.setText(workspace)
            self.workspace_label.setToolTip(workspace)
            self.stack.setCurrentWidget(self.tabs)
            self.header.show()
            self.workspace_label.show()
            self.status.show()
            self.footer.show()
            self.workspace_name.setText("Workspace: " + workspace)
            self.tabs.setCurrentIndex(0)
            self.discover()
            self.refresh_records()

        def failed(error):
            self.login.set_loading(False)
            if saved:
                self.clear_saved_credentials()
                self.key.clear()
            self.login.set_error(str(error))

        self.submit("Connecting…", client.validate, done, failed)

    def disconnect(self):
        from eodh_qgis.raster_loader import clear_stream_credentials

        clear_stream_credentials()
        self.epoch += 1
        for task in self.tasks:
            task.cancel()
        self.client = None
        self.key.clear()
        self.clear_results()
        self.records = []
        self.record_cards = []
        self.orders.clear()
        self.set_bbox(None)
        self.cleanup_map()
        self.clear_saved_credentials()
        self.header.hide()
        self.workspace_label.hide()
        self.status.hide()
        self.footer.hide()
        self.login.set_loading(False)
        self.login.set_error("")
        self.stack.setCurrentIndex(0)
        self.workspace_label.setText("Earth Observation Data Hub")
        self.status.setText("Signed out. Saved credentials cleared.")
        self.progress.hide()

    def clear_saved_credentials(self):
        if self.auth_id:
            QgsApplication.authManager().removeAuthenticationConfig(self.auth_id)
            QtCore.QSettings().remove("eodh/hub_auth")
            self.auth_id = ""

    def submit(self, title, work, done, failed=None, with_task=False, quiet=False):
        epoch = self.epoch
        if not quiet:
            self.status.setText(title)
            self.progress.setRange(0, 0)
            self.progress.setVisible(self.client is not None)

        def finish(result, error):
            if task in self.tasks:
                self.tasks.remove(task)
            if epoch != self.epoch:
                return
            if not quiet:
                self.progress.hide()
            if error is not None:
                if failed:
                    failed(error)
                if not quiet:
                    self.status.setText(str(error))
                if isinstance(error, HubError) and error.status == 401 and self.client:
                    self.disconnect()
                    self.status.setText(str(error))
                    self.login.set_error(str(error))
            else:
                if not quiet:
                    self.status.setText("Ready")
                    self.progress.hide()
                done(result)

        task = HubTask(title, work, finish)
        if with_task:
            task.work = lambda: work(task)

            def report(name, downloaded, total):
                if epoch != self.epoch:
                    return
                suffix = f" / {total / 1048576:.1f} MB" if total else ""
                self.status_detail.setText(f"Downloading {downloaded / 1048576:.1f} MB{suffix}...")
                self.status_percent.setText(f"{min(100, int(100 * downloaded / total))}%" if total else "")
                if total:
                    self.progress.setRange(0, 100)
                    self.progress.setValue(min(100, int(100 * downloaded / total)))

            def stage(message):
                if epoch == self.epoch:
                    self.status_detail.setText(message)
                    self.status_percent.clear()
                    self.progress.setRange(0, 0)

            task.asset_stage.connect(stage)
            task.download_progress.connect(report)
        self.tasks.append(task)
        QgsApplication.taskManager().addTask(task)

    def build_search(self):
        _, layout = self.page("Search")
        layout.setSpacing(4)
        layout.addWidget(text_label("Catalog", 12, True))
        self.catalogue = ScrollComboBox()
        self.catalogue.addItems(("Public", "Commercial"))
        self.catalogue.currentTextChanged.connect(self.discover)
        layout.addWidget(self.catalogue)
        self.commercial_help = hyperlink(
            "Learn about commercial bundles and licences",
            "https://docs.eodatahub.org.uk/Analysts/commercial/ordering-commercial-data/#understanding-the-ordering-options",
        )
        self.commercial_help.hide()
        layout.addWidget(self.commercial_help)
        layout.addWidget(text_label("Collection", 12, True))
        self.collection = ScrollComboBox()
        self.collection.setEditable(True)
        self.collection.setMaxVisibleItems(20)
        self.collection.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        self.collection.currentIndexChanged.connect(self.collection_changed)
        layout.addWidget(self.collection)
        self.collection_progress = busy_bar()
        layout.addWidget(self.collection_progress)
        layout.addWidget(
            text_label("Collections are discovered recursively from the selected curated catalogue.", 10, color="#777")
        )
        layout.addSpacing(8)
        layout.addWidget(text_label("Area of Interest", 12, True))
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)
        for text, action in (
            ("Draw on Map", self.draw),
            ("Map Extent", self.map_extent),
            ("Import AOI", self.import_aoi),
            ("Clear", lambda: self.set_bbox(None)),
        ):
            control = button(text, action)
            control.setStyleSheet("padding:3px 4px;")
            row.addWidget(control, 1)
            if text == "Clear":
                self.clear_aoi_button = control
                control.setEnabled(False)
        layout.addLayout(row)
        self.aoi_text = text_label("No area selected", 11, color="#777")
        layout.addWidget(self.aoi_text)
        layout.addSpacing(8)
        layout.addWidget(text_label("Date Range", 12, True))
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(4)
        self.start = QtWidgets.QDateEdit(QtCore.QDate.currentDate().addMonths(-1))
        self.end = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        for widget in (self.start, self.end):
            widget.setCalendarPopup(True)
            widget.setDisplayFormat(QtCore.QLocale().dateFormat(QtCore.QLocale.FormatType.ShortFormat))
            calendar = (Path(__file__).parents[1] / "brand" / "calendar.svg").as_posix()
            widget.setStyleSheet(
                "QDateEdit::drop-down {width:22px;border:0;} "
                f'QDateEdit::down-arrow {{image:url("{calendar}");width:16px;height:16px;}}'
            )
        row.addWidget(self.start, 1)
        row.addWidget(label(" to "))
        row.addWidget(self.end, 1)
        layout.addLayout(row)
        layout.addSpacing(8)
        self.cloud_group = QtWidgets.QWidget()
        group = QtWidgets.QVBoxLayout(self.cloud_group)
        group.setContentsMargins(0, 0, 0, 0)
        group.setSpacing(4)
        group.addWidget(text_label("Max Cloud Cover", 12, True))
        row = QtWidgets.QHBoxLayout()
        self.cloud = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.cloud.setRange(0, 100)
        self.cloud.setValue(100)
        self.cloud.setTickInterval(10)
        self.cloud_text = label("100%")
        self.cloud_text.setFixedWidth(45)
        self.cloud_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.cloud.valueChanged.connect(lambda value: self.cloud_text.setText(f"{value}%"))
        row.addWidget(self.cloud, 1)
        row.addWidget(self.cloud_text)
        group.addLayout(row)
        group.addWidget(text_label("This collection publishes cloud-cover metadata.", 10, color="#777"))
        group.addSpacing(8)
        layout.addWidget(self.cloud_group)
        self.cloud_group.hide()
        self.search_button = button("Search", self.search)
        font = self.search_button.font()
        font.setWeight(QtGui.QFont.Weight.DemiBold)
        self.search_button.setFont(font)
        self.search_button.setStyleSheet("padding:6px 8px;")
        self.search_button.setEnabled(False)
        layout.addWidget(self.search_button)
        self.search_progress = busy_bar()
        layout.addWidget(self.search_progress)
        self.search_summary = text_label("", 11, color="#777")
        layout.addWidget(self.search_summary)
        layout.addStretch()

    def discover(self, *args):
        root = self.catalogue.currentText()
        self.commercial_help.setVisible(root == "Commercial")
        if not self.client:
            return
        self.discovery_id += 1
        generation = self.discovery_id
        self.collection.clear()
        self.search_button.setEnabled(False)
        self.clear_results()
        self.collection_progress.show()
        self.search_summary.setText(f"Loading {root} collections...")
        client = self.client

        def done(entries):
            if generation != self.discovery_id:
                return
            self.collection_progress.hide()
            self.collection.blockSignals(True)
            for entry in entries:
                self.collection.addItem(entry["label"], entry)
            self.collection.blockSignals(False)
            self.collection_changed()
            self.search_summary.setText(
                f"Loaded {len(entries)} {root} collections."
                if entries
                else f"No collections are available under {root}."
            )

        def failed(error):
            if generation == self.discovery_id:
                self.collection_progress.hide()
                self.search_summary.setText(f"Failed to load {root} collections: {error}")

        self.submit("Loading collections...", lambda: client.discover(root), done, failed, quiet=True)

    def collection_changed(self, *args):
        entry = self.collection.currentData()
        self.search_button.setEnabled(bool(entry) and self.bbox is not None)
        self.cloud_group.hide()
        self.cloud.setValue(100)
        if not entry:
            return
        extent = entry["collection"].get("extent") or {}
        intervals = (extent.get("temporal") or {}).get("interval") or []
        starts = [date for i in intervals if i and (date := parsed_date(i[0])) is not None]
        ends = [date for i in intervals if len(i) > 1 and (date := parsed_date(i[1])) is not None]
        self.start.setDate(QtCore.QDate(min(starts).date()) if starts else QtCore.QDate.currentDate().addMonths(-1))
        self.end.setDate(QtCore.QDate(max(ends).date()) if ends else QtCore.QDate.currentDate())
        bounds = [b for raw in (extent.get("spatial") or {}).get("bbox", []) if (b := bbox2d(raw))]
        if bounds:
            bbox = [
                min(b[0] for b in bounds),
                min(b[1] for b in bounds),
                max(b[2] for b in bounds),
                max(b[3] for b in bounds),
            ]
            self.set_bbox(bbox, "Collection extent", collection=True)
        elif self.aoi_from_collection:
            self.set_bbox(None)
        if self.client:
            client = self.client

            def done(supported):
                if self.collection.currentData() == entry:
                    self.cloud_group.setVisible(supported)

            self.submit(
                "Checking available filters...",
                lambda: client.cloud_supported(entry),
                done,
                lambda error: None,
                quiet=True,
            )

    def set_bbox(self, bbox, source="Drawn AOI", collection=False):
        try:
            self.bbox = validate_bbox(bbox) if bbox is not None else None
        except ValueError as error:
            self.search_summary.setText(str(error))
            return
        self.aoi_from_collection = collection
        self.clear_aoi_button.setEnabled(self.bbox is not None)
        self.search_button.setEnabled(self.bbox is not None and bool(self.collection.currentData()))
        self.aoi_text.setText(
            f"{source}: {self.bbox[0]:.2f}, {self.bbox[1]:.2f} to {self.bbox[2]:.2f}, {self.bbox[3]:.2f}"
            if self.bbox
            else "No area selected"
        )
        for card in self.result_cards:
            if card.commercial:
                card.commercial.invalidate()
        if self.bbox is None:
            self.show_footprints.setChecked(False)
        self.overlays.show_aoi(self.bbox, self.show_aoi.isChecked() and self.isVisible())

    def draw(self):
        if self.iface.mapCanvas().mapTool() != self.draw_tool:
            self.previous_tool = self.iface.mapCanvas().mapTool()
        self.iface.mapCanvas().setMapTool(self.draw_tool)

    def drawn(self, rect):
        try:
            self.set_bbox(self.overlays.extent_wgs84(rect))
        except Exception as error:
            self.search_summary.setText(f"Failed to draw AOI: {error}")
        if self.previous_tool:
            self.iface.mapCanvas().setMapTool(self.previous_tool)
        else:
            self.iface.mapCanvas().unsetMapTool(self.draw_tool)

    def map_extent(self):
        try:
            self.set_bbox(self.overlays.extent_wgs84(self.iface.mapCanvas().extent()), "Map extent")
        except Exception as error:
            self.search_summary.setText(f"Failed to get map extent: {error}")

    def import_aoi(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import AOI",
            "",
            "Supported AOI files (*.geojson *.json *.shp *.gpkg);;GeoJSON files (*.geojson *.json);;Shapefiles (*.shp);;GeoPackages (*.gpkg)",
        )
        if path:
            try:
                self.import_aoi_path(path)
            except Exception as error:
                self.search_summary.setText(f"Failed to import AOI: {error}")

    def import_aoi_path(self, path):
        if Path(path).suffix.lower() in (".json", ".geojson"):
            doc = json.loads(Path(path).read_text(encoding="utf-8-sig"))
            features = doc.get("features", [doc]) if doc.get("type") == "FeatureCollection" else [doc]
            geoms = [g for f in features if (g := geometry(f.get("geometry", f)))]
            if not geoms:
                raise ValueError("GeoJSON must contain valid Polygon or MultiPolygon geometries.")
            rect = geoms[0].boundingBox()
            for geom in geoms[1:]:
                rect.combineExtentWith(geom.boundingBox())
            self.set_bbox([rect.xMinimum(), rect.yMinimum(), rect.xMaximum(), rect.yMaximum()], "Imported AOI")
            return
        sources = (
            [
                entry.uri()
                for entry in QgsProviderRegistry.instance().querySublayers(str(path))
                if entry.providerKey() == "ogr"
            ]
            if Path(path).suffix.lower() == ".gpkg"
            else [str(path)]
        )
        rect = None
        for source in sources:
            layer = QgsVectorLayer(source, "AOI", "ogr")
            if not layer.isValid() or not layer.isSpatial() or layer.featureCount() == 0:
                continue
            if not layer.crs().isValid():
                raise ValueError("The AOI file has no coordinate reference system.")
            transform = QgsCoordinateTransform(layer.crs(), WGS84, QgsProject.instance())
            bounds = transform.transformBoundingBox(layer.extent())
            if rect is None:
                rect = bounds
            else:
                rect.combineExtentWith(bounds)
        if rect is None:
            raise ValueError("The AOI file contains no readable spatial features.")
        self.set_bbox(
            [rect.xMinimum(), rect.yMinimum(), rect.xMaximum(), rect.yMaximum()], f"Imported AOI ({Path(path).name})"
        )

    def tab_page(self, title):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.tabs.addTab(page, title)
        return layout

    def build_results(self):
        layout = self.tab_page("Results")
        self.timeline = Timeline()
        self.timeline.selected.connect(self.select_timeline)
        layout.addWidget(self.timeline)
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(8, 5, 8, 2)
        row.setSpacing(16)
        self.show_footprints = QtWidgets.QCheckBox("Show footprints")
        self.show_footprints.setChecked(True)
        self.show_footprints.toggled.connect(self.update_overlays)
        self.show_aoi = QtWidgets.QCheckBox("Show AOI")
        self.show_aoi.setChecked(True)
        self.show_aoi.toggled.connect(self.update_overlays)
        row.addWidget(self.show_footprints)
        row.addWidget(self.show_aoi)
        row.addStretch()
        layout.addLayout(row)
        self.results_empty = text_label("No results found", 13, True, "#777")
        self.results_empty.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop)
        self.results_empty.setContentsMargins(0, 24, 0, 0)
        layout.addWidget(self.results_empty, 1)
        self.results = CardList()
        self.results.currentRowChanged.connect(self.select_result)
        self.results.hide()
        layout.addWidget(self.results, 1)
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(8)
        self.summary = text_label("", 11, color="#777")
        row.addWidget(self.summary, 1)
        self.previous = button("\u2039 Previous", self.previous_page)
        self.next = button("Next \u203a", self.next_page)
        self.page_label = label("")
        row.addWidget(self.previous)
        row.addWidget(self.page_label)
        row.addWidget(self.next)
        layout.addLayout(row)
        self.pagination_error = text_label("", 10, color="#b22222")
        self.pagination_error.setContentsMargins(8, 0, 8, 4)
        self.pagination_error.hide()
        layout.addWidget(self.pagination_error)
        for widget in (self.previous, self.next, self.page_label):
            widget.hide()

    def clear_results(self):
        self.search_id += 1
        self.selection_id += 1
        for card in self.result_cards:
            if card.commercial:
                card.commercial.request_id += 1
        self.items, self.next_link, self.pages, self.result_cards = [], None, [], []
        self.page_index = 0
        self.results.clear()
        self.results.hide()
        self.results_empty.show()
        self.timeline.set_items([])
        self.summary.clear()
        self.pagination_error.hide()
        for widget in (self.previous, self.next, self.page_label):
            widget.hide()
        self.overlays.clear()

    def search(self):
        entry = self.collection.currentData()
        if not entry or not self.client or self.bbox is None:
            return
        try:
            params = search_body(
                entry["collection"]["id"],
                self.start.date().toString("yyyy-MM-dd"),
                self.end.date().toString("yyyy-MM-dd"),
                self.bbox,
                self.cloud.value() if not self.cloud_group.isHidden() else 100,
            )
        except ValueError as error:
            self.search_summary.setText(f"Search failed: {error}")
            return
        self.clear_results()
        self.search_params = params
        client, generation = self.client, self.search_id
        self.search_button.setEnabled(False)
        self.search_progress.show()
        self.search_summary.setText("Searching...")

        def done(page):
            if generation == self.search_id:
                self.search_button.setEnabled(True)
                self.search_progress.hide()
                self.pages = [page]
                self.display_page(page)
                self.search_summary.setText(f"Found {self.total_count} items ({len(page.get('features', []))} shown).")
                self.tabs.setCurrentIndex(1)

        def failed(error):
            if generation == self.search_id:
                self.search_button.setEnabled(True)
                self.search_progress.hide()
                self.search_summary.setText(f"Search failed: {error}")

        self.submit("Searching...", lambda: client.request(entry["search"], "POST", params), done, failed, quiet=True)

    def display_page(self, page):
        self.selection_id += 1
        self.current_page = page
        raw_items = page.get("features", [])
        self.items = [item for item in raw_items if overlap(item.get("bbox"), self.bbox) != 0]
        filtered = len(raw_items) - len(self.items)
        self.next_link = link(page, "next")
        self.results.blockSignals(True)
        for card in self.result_cards:
            if card.commercial:
                card.commercial.request_id += 1
        self.result_cards = []
        self.results.clear()
        entry = self.collection.currentData() or {}
        licence = entry.get("collection", {}).get("license")
        for index, item in enumerate(self.items):
            card = ResultCard(self, item, licence)
            card.selected.connect(lambda i=index: self.results.setCurrentRow(i))
            self.result_cards.append(card)
            self.results.add_card(card)
        self.results.blockSignals(False)
        fallback_total = getattr(self, "total_count", len(raw_items)) if self.page_index else len(raw_items)
        self.total_count = next(
            (
                value
                for value in (
                    (page.get("context") or {}).get("matched"),
                    page.get("numberMatched"),
                    page.get("numMatched"),
                )
                if isinstance(value, int) and value >= 0
            ),
            fallback_total,
        )
        excluded = f"; {filtered} outside AOI excluded" if filtered else ""
        self.summary.setText(f"{len(self.items)} results ({self.total_count} total{excluded})")
        self.page_label.setText(f"Page {self.page_index + 1} of {max(1, (self.total_count + 49) // 50)}")
        self.next.setEnabled(bool(self.next_link) or self.page_index < len(self.pages) - 1)
        self.previous.setEnabled(self.page_index > 0)
        for widget in (self.previous, self.next, self.page_label):
            widget.show()
        self.pagination_error.hide()
        self.results.setVisible(bool(self.items))
        self.results_empty.setVisible(not self.items)
        self.timeline.set_items(self.items)
        index = self.timeline.order[-1] if self.timeline.order else -1
        self.results.setCurrentRow(index)
        self.select_result(index)
        self.request_thumbnails()
        QtCore.QTimer.singleShot(0, self.results.fit_cards)

    def next_page(self):
        if self.page_index < len(self.pages) - 1:
            self.page_index += 1
            self.display_page(self.pages[self.page_index])
            return
        if not self.next_link or not self.client:
            return
        client, entry, current, generation = self.client, dict(self.next_link), self.current_page, self.search_id
        target = self.page_index + 1
        self.next.setEnabled(False)
        self.previous.setEnabled(False)
        self.page_label.setText(f"Loading page {target + 1}...")

        def done(page):
            if generation == self.search_id:
                self.pages.append(page)
                self.page_index = target
                self.display_page(page)

        def failed(error):
            if generation == self.search_id:
                self.pagination_error.setText(f"Could not load page {target + 1}: {error}")
                self.pagination_error.show()
                self.next.setEnabled(True)
                self.previous.setEnabled(self.page_index > 0)
                self.page_label.setText(f"Page {self.page_index + 1} of {max(1, (self.total_count + 49) // 50)}")

        self.submit(
            "Loading page...",
            lambda: client.page(entry, self.search_params, current.get("_url")),
            done,
            failed,
            quiet=True,
        )

    def previous_page(self):
        if self.page_index > 0:
            self.page_index -= 1
            self.display_page(self.pages[self.page_index])

    def select_timeline(self, index):
        self.results.setCurrentRow(index)
        if 0 <= index < self.results.count():
            self.results.scrollToItem(self.results.item(index))

    def select_result(self, index):
        self.timeline.select(index)
        for i, card in enumerate(self.result_cards):
            card.set_selected(i == index)
        self.update_overlays()

    def request_thumbnails(self):
        if not self.client:
            return
        client, generation, epoch = self.client, self.selection_id, self.epoch
        items = list(self.items)

        def work():
            for index, item in enumerate(items):
                if task.isCanceled():
                    break
                asset = thumbnail_asset(item)
                if asset and asset.get("href"):
                    try:
                        data = client.request(urljoin(href(item, "self") or client.base, asset["href"]), raw=True)
                        task.thumbnail_ready.emit(index, data)
                    except Exception:
                        # Thumbnails are optional. Keep loading the remaining results,
                        # but record failures without exposing signed URLs or credentials.
                        QgsMessageLog.logMessage(
                            f"Could not load thumbnail for result {index + 1}. The result remains available.",
                            "EODH",
                            Qgis.MessageLevel.Warning,
                            notifyUser=False,
                        )

        def ready(index, data):
            if generation != self.selection_id or epoch != self.epoch:
                return
            pixmap = QtGui.QPixmap()
            if pixmap.loadFromData(data):
                self.result_cards[index].set_thumbnail(pixmap)
                self.timeline.set_thumbnail(index, pixmap)

        def finished(result, error):
            if task in self.tasks:
                self.tasks.remove(task)

        task = HubTask("EODH thumbnails", work, finished)
        task.thumbnail_ready.connect(ready)
        self.tasks.append(task)
        QgsApplication.taskManager().addTask(task)

    def update_overlays(self, *args):
        self.overlays.footprints(
            self.items, self.results.currentRow(), self.show_footprints.isChecked() and self.isVisible()
        )
        self.overlays.show_aoi(self.bbox, self.show_aoi.isChecked() and self.isVisible())

    def load_quick_view(self, card):
        if not self.client or card.loading:
            return
        render = quick_view(card.item, self.client.base)
        if not render:
            return
        url, title = render
        card.loading = True
        card.update_enabled()
        self.status.setText(f"1 of 1: {title} (Quick view)")
        self.status_detail.setText("Opening Quick view in QGIS...")
        self.progress.show()
        try:
            uri = "type=xyz&url=" + quote(url, safe="")
            if self.auth_id:
                uri += "&authcfg=" + quote(self.auth_id, safe="")
            name = f"Quick view - {card.item.get('collection') or 'item'} - {card.item.get('id', '')[:60]} ({title})"[
                :128
            ]
            layer = QgsRasterLayer(uri, name, "wms")
            if not layer.isValid():
                raise HubError("Quick view could not be opened.")
            canvas = self.iface.mapCanvas()
            previous_extent, previous_crs = canvas.extent(), canvas.mapSettings().destinationCrs()
            QgsProject.instance().addMapLayer(layer)
            # QGIS resets an empty map to the XYZ world's extent when its first
            # layer arrives. Preserve the user's view, as ArcGIS does.
            transform = QgsCoordinateTransform(
                previous_crs, canvas.mapSettings().destinationCrs(), QgsProject.instance()
            )
            canvas.setExtent(transform.transformBoundingBox(previous_extent))
            canvas.refresh()
            self.status.setText("Asset loaded")
            self.status_detail.setText(f"Added {title} to the map.")
        except Exception as error:
            self.status.setText("Asset load failed")
            self.status_detail.setText(str(error))
            QtWidgets.QMessageBox.warning(
                self, "EODH - Quick View Error", f"Failed to open Quick view for this item.\n\n{error}"
            )
        finally:
            card.loading = False
            card.update_enabled()
            self.progress.hide()

    def load_card(self, card):
        if not self.client or card.loading or not card.assets.selected():
            return
        if isinstance(card, WorkspaceCard) and not card.can_load:
            return
        client, item, selected = self.client, card.item, card.assets.selected()
        card.loading = True
        card.update_enabled()
        gui_thread = QtCore.QCoreApplication.instance().thread()

        def finish_card():
            try:
                card.loading = False
                card.update_enabled()
            except RuntimeError:
                pass
            self.status_percent.clear()

        def failed(error):
            finish_card()
            self.status.setText("Asset load failed")
            self.status_detail.setText(str(error))

        def start(batch, download=False):
            def work(task):
                from eodh_qgis.raster_loader import StreamingUnavailable, load_asset

                loaded, fallback, errors = [], [], []
                for index, (key, asset) in enumerate(batch, 1):
                    if task.isCanceled():
                        raise HubError("Asset loading cancelled.")
                    url = urljoin(href(item, "self") or client.base, asset["href"])
                    name = f"{item.get('id')}_{key}"
                    local = download or asset_type(asset) == "NetCDF"
                    stage = "Downloading full file" if local else "Opening remote raster"
                    task.asset_stage.emit(f"{index} of {len(batch)}: {stage} — {key}...")

                    def report(received, total):
                        if task.isCanceled():
                            raise HubError("Asset loading cancelled.")
                        task.download_progress.emit(key, received, total)

                    try:
                        layers, streamed = load_asset(client, url, asset, name, download=download, progress=report)
                        # Serialize while the worker's PROJ context still exists.
                        # Moving the QObject does not transfer that thread-local
                        # context; its CRS can otherwise turn empty on pool expiry.
                        loaded.append((layers, key, streamed, [layer.crs().toWkt() for layer in layers]))
                    except StreamingUnavailable as error:
                        fallback.append((key, asset, str(error)))
                    except Exception as error:
                        errors.append(f"Failed to load asset '{key}' ({asset_type(asset)}).\n\nError: {error}")
                # Layers are exclusively owned by this worker until this point.
                # The main-thread callback is the only code that adds them to QGIS.
                for layers, _, _, _ in loaded:
                    for layer in layers:
                        layer.moveToThread(gui_thread)
                return loaded, fallback, errors

            def done(result):
                loaded, fallback, errors = result
                for layers, key, streamed, definitions in loaded:
                    for layer, wkt in zip(layers, definitions):
                        if wkt:
                            crs = QgsCoordinateReferenceSystem.fromWkt(wkt)
                            # setCrs skips equal EPSG identifiers, even if the old
                            # thread-local definition is gone. Force a fresh copy.
                            layer.setCrs(QgsCoordinateReferenceSystem())
                            layer.setCrs(crs)
                        QgsProject.instance().addMapLayer(layer)
                    self.status.setText("Asset loaded")
                    self.status_detail.setText(
                        f"Streaming {key} — map tiles load as you pan and zoom."
                        if streamed
                        else f"Added {key} to the map."
                    )
                if fallback:
                    if errors:
                        QtWidgets.QMessageBox.warning(self, "EODH — Asset Load Error", "\n\n".join(errors))
                    start([(key, asset) for key, asset, _ in fallback], download=True)
                    return
                finish_card()
                if errors:
                    failed(errors[-1])
                    QtWidgets.QMessageBox.warning(self, "EODH — Asset Load Error", "\n\n".join(errors))

            self.submit("Loading assets...", work, done, failed, with_task=True)

        start(selected)

    def build_workspace(self):
        layout = self.tab_page("Workspace")
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(8, 8, 8, 4)
        title = QtWidgets.QVBoxLayout()
        title.setSpacing(0)
        title.addWidget(text_label("Commercial data", 14, True))
        self.workspace_name = text_label("Workspace: ", 10, color="#666")
        title.addWidget(self.workspace_name)
        row.addLayout(title, 1)
        self.refresh_button = button("Refresh", self.refresh_records)
        row.addWidget(self.refresh_button)
        layout.addLayout(row)
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(4)
        self.provider_filter, self.status_filter = ScrollComboBox(), ScrollComboBox()
        for title, widget in (("Provider:", self.provider_filter), ("Status:", self.status_filter)):
            row.addWidget(text_label(title))
            widget.addItem("All")
            widget.currentTextChanged.connect(self.filter_records)
            row.addWidget(widget, 1)
        layout.addLayout(row)
        self.workspace_progress = busy_bar()
        layout.addWidget(self.workspace_progress)
        self.workspace_error = text_label("", 11, color="red")
        self.workspace_error.setContentsMargins(8, 6, 8, 5)
        self.workspace_error.hide()
        layout.addWidget(self.workspace_error)
        self.workspace_retry = button("Retry", self.refresh_records)
        self.workspace_retry.hide()
        layout.addWidget(self.workspace_retry, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        self.workspace_empty = label("No commercial order records were found in this workspace.")
        self.workspace_empty.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop)
        self.workspace_empty.setContentsMargins(18, 24, 18, 0)
        self.workspace_empty.setStyleSheet("color:#777;")
        layout.addWidget(self.workspace_empty, 1)
        self.orders = CardList()
        self.orders.setContentsMargins(8, 0, 8, 0)
        self.orders.hide()
        layout.addWidget(self.orders, 1)

    def refresh_records(self):
        if not self.client:
            return
        self.workspace_generation += 1
        generation = self.workspace_generation
        client = self.client
        self.workspace_progress.show()
        self.workspace_empty.hide()
        self.workspace_error.hide()
        self.workspace_retry.hide()
        self.refresh_button.setEnabled(False)

        def done(records):
            if generation != self.workspace_generation:
                return
            self.records = records
            self.workspace_progress.hide()
            self.refresh_button.setEnabled(True)
            for widget, values in (
                (self.provider_filter, {r["_provider"] for r in records}),
                (self.status_filter, {record_status(r) for r in records}),
            ):
                selected = widget.currentText()
                widget.blockSignals(True)
                widget.clear()
                widget.addItems(["All", *sorted(values, key=str.casefold)])
                widget.setCurrentText(selected if selected in values else "All")
                widget.blockSignals(False)
            self.filter_records()

        def failed(error):
            if generation != self.workspace_generation:
                return
            self.workspace_progress.hide()
            self.refresh_button.setEnabled(True)
            self.records = []
            self.filter_records()
            self.workspace_empty.hide()
            self.workspace_error.setText(str(error))
            self.workspace_error.show()
            self.workspace_retry.show()

        self.submit("Loading workspace commercial data...", client.records, done, failed, quiet=True)

    def filter_records(self, *args):
        for card in self.record_cards:
            card.item["_ui_selected"] = [key for key, asset in card.assets.selected()]
            card.item["_ui_expanded"] = card.expand.isChecked()
        self.record_cards = []
        self.orders.clear()
        p, s = self.provider_filter.currentText(), self.status_filter.currentText()
        for item in self.records:
            if p != "All" and item["_provider"].casefold() != p.casefold():
                continue
            if s != "All" and record_status(item).casefold() != s.casefold():
                continue
            card = WorkspaceCard(self, item)
            if "_ui_selected" in item:
                for box, key, _asset in card.assets.boxes:
                    box.setChecked(key in item["_ui_selected"])
            card.expand.setChecked(item.get("_ui_expanded", False))
            self.record_cards.append(card)
            self.orders.add_card(card)
        self.orders.setVisible(bool(self.record_cards))
        self.workspace_empty.setVisible(not self.record_cards)

    def cleanup_map(self):
        self.overlays.clear()
        self.overlays.clear_aoi()
        canvas = self.iface.mapCanvas()
        if canvas.mapTool() == self.draw_tool:
            if self.previous_tool:
                canvas.setMapTool(self.previous_tool)
            else:
                canvas.unsetMapTool(self.draw_tool)

    def visibility_changed(self, visible):
        if not visible:
            self.cleanup_map()

    def shutdown(self):
        self.epoch += 1
        for task in self.tasks:
            task.cancel()
        self.cleanup_map()
        self.iface.mapCanvas().destinationCrsChanged.disconnect(self.update_overlays)
        self.iface.mapCanvas().scene().removeItem(self.draw_tool.band)
        self.client = None
        self.key.clear()
        self.hide()
