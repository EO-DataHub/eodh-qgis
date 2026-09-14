"""Dockable, asynchronous Search / Results / Workspace interface."""

import json
from pathlib import Path
from urllib.parse import urljoin

from qgis.core import QgsApplication, QgsAuthMethodConfig, QgsProject, QgsRasterLayer, QgsTask
from qgis.PyQt import QtCore, QtGui, QtWidgets

from eodh_qgis.api.hub import (
    COMPLETED,
    ENVIRONMENTS,
    HubClient,
    HubError,
    asset_type,
    href,
    link,
    property_value,
    record_status,
    search_body,
    validate_bbox,
)

from .hub_login import LoginPage
from .hub_map import Overlays, RectangleTool, geometry
from .hub_widgets import CommercialPanel, Timeline, button, label


class HubTask(QgsTask):
    download_progress = QtCore.pyqtSignal(str, object, object)

    def __init__(self, title, work, finish):
        super().__init__(title, QgsTask.Flag.CanCancel)
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
        super().__init__("EODH", parent or iface.mainWindow())
        self.setObjectName("EodhHubDock")
        self.iface, self.client = iface, None
        self.epoch, self.discovery_id, self.search_id, self.selection_id = 0, 0, 0, 0
        self.tasks, self.items, self.records, self.history = [], [], [], []
        self.asset_busy = False
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
        header.setContentsMargins(12, 10, 12, 10)
        mark = QtWidgets.QLabel()
        mark.setPixmap(
            QtGui.QPixmap(str(Path(__file__).parents[1] / "brand" / "eodh-logo-colour.png")).scaledToWidth(
                145, QtCore.Qt.TransformationMode.SmoothTransformation
            )
        )
        header.addWidget(mark)
        header.addStretch()
        header.addWidget(button("Usage guide", self.show_guide))
        self.sign_out = button("Sign Out", self.disconnect)
        header.addWidget(self.sign_out)
        self.header.hide()
        layout.addWidget(self.header)
        self.workspace_label = label("Earth Observation Data Hub")
        self.workspace_label.setContentsMargins(12, 0, 12, 6)
        self.workspace_label.hide()
        layout.addWidget(self.workspace_label)
        self.stack = QtWidgets.QStackedWidget()
        layout.addWidget(self.stack, 1)
        self.status = label("Ready")
        self.status.setAccessibleName("EODH status")
        self.status.setContentsMargins(12, 4, 12, 10)
        self.status.hide()
        layout.addWidget(self.status)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(3)
        self.progress.hide()
        layout.addWidget(self.progress)
        self.root.setStyleSheet(
            "QPushButton#primary {background:#4c72ba;color:white;padding:7px;} "
            "QPushButton#primary:disabled {background:#8b9fbe;} "
            "QGroupBox {font-weight:600;margin-top:10px;padding-top:10px;} "
            "QLineEdit,QComboBox,QDateEdit {min-height:24px;}"
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
        layout.setContentsMargins(9, 12, 9, 9)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        self.tabs.addTab(scroll, title)
        return page, layout

    def build_login(self):
        self.login = LoginPage(self.connect_workspace)
        self.workspace, self.key = self.login.workspace, self.login.key
        self.connect_button = self.login.connect_button
        self.login_scroll = QtWidgets.QScrollArea()
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
            self.workspace_label.setText(workspace + " • Production")
            self.stack.setCurrentWidget(self.tabs)
            self.header.show()
            self.workspace_label.show()
            self.status.show()
            self.discover()

        def failed(error):
            self.login.set_loading(False)
            if saved:
                self.clear_saved_credentials()
                self.key.clear()
            self.login.set_error(str(error))

        self.submit("Connecting…", client.validate, done, failed)

    def disconnect(self):
        self.epoch += 1
        self.asset_busy = False
        for task in self.tasks:
            task.cancel()
        self.client = None
        self.key.clear()
        self.clear_results()
        self.records = []
        self.orders.clear()
        self.order_assets.clear()
        self.set_bbox(None)
        self.cleanup_map()
        self.clear_saved_credentials()
        self.header.hide()
        self.workspace_label.hide()
        self.status.hide()
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

    def submit(self, title, work, done, failed=None, with_task=False):
        epoch = self.epoch
        self.status.setText(title)
        self.progress.setRange(0, 0)
        self.progress.setVisible(self.client is not None)

        def finish(result, error):
            if task in self.tasks:
                self.tasks.remove(task)
            self.progress.setVisible(bool(self.tasks) and self.client is not None)
            if epoch != self.epoch:
                return
            if error is not None:
                if failed:
                    failed(error)
                self.status.setText(str(error))
                if isinstance(error, HubError) and error.status == 401 and self.client:
                    self.disconnect()
                    self.status.setText(str(error))
                    self.login.set_error(str(error))
            else:
                self.status.setText("Ready")
                done(result)

        task = HubTask(title, work, finish)
        if with_task:
            task.work = lambda: work(task)

            def report(name, downloaded, total):
                if epoch != self.epoch:
                    return
                suffix = f" / {total / 1048576:.1f} MB" if total else ""
                self.status.setText(f"{name}: {downloaded / 1048576:.1f} MB{suffix}")
                if total:
                    self.progress.setRange(0, 100)
                    self.progress.setValue(min(100, int(100 * downloaded / total)))

            task.download_progress.connect(report)
        self.tasks.append(task)
        QgsApplication.taskManager().addTask(task)

    def build_search(self):
        _, layout = self.page("Search")
        layout.addWidget(label("Catalogue"))
        self.catalogue = QtWidgets.QComboBox()
        self.catalogue.addItems(("Public", "Commercial"))
        self.catalogue.currentTextChanged.connect(self.discover)
        layout.addWidget(self.catalogue)
        layout.addWidget(label("Collection"))
        self.collection = QtWidgets.QComboBox()
        self.collection.setEditable(True)
        self.collection.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        self.collection.currentIndexChanged.connect(self.collection_changed)
        layout.addWidget(self.collection)
        layout.addWidget(label("Collections are discovered recursively from the selected curated catalogue."))
        layout.addWidget(button("Refresh collections / Retry", self.discover))
        self.collection_description = label("")
        self.collection_description.hide()
        details_toggle = QtWidgets.QCheckBox("Collection details")
        details_toggle.toggled.connect(self.collection_description.setVisible)
        layout.addWidget(details_toggle)
        layout.addWidget(self.collection_description)
        group = QtWidgets.QGroupBox("Area of Interest")
        aoi_layout = QtWidgets.QVBoxLayout(group)
        row = QtWidgets.QGridLayout()
        for index, (text, action) in enumerate(
            (
                ("Draw on Map", self.draw),
                ("Map Extent", self.map_extent),
                ("Import GeoJSON", self.import_aoi),
                ("Clear", lambda: self.set_bbox(None)),
            )
        ):
            row.addWidget(button(text, action), index // 2, index % 2)
        aoi_layout.addLayout(row)
        self.aoi_text = label("No area of interest")
        aoi_layout.addWidget(self.aoi_text)
        layout.addWidget(group)
        layout.addWidget(label("Date Range"))
        row = QtWidgets.QHBoxLayout()
        self.start = QtWidgets.QDateEdit(QtCore.QDate.currentDate().addMonths(-2))
        self.end = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        for widget in (self.start, self.end):
            widget.setCalendarPopup(True)
            widget.setDisplayFormat("yyyy-MM-dd")
        row.addWidget(self.start)
        row.addWidget(label("to"))
        row.addWidget(self.end)
        layout.addLayout(row)
        self.cloud_group = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(self.cloud_group)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(label("Max Cloud Cover"))
        self.cloud = QtWidgets.QSpinBox()
        self.cloud.setRange(0, 100)
        self.cloud.setValue(100)
        self.cloud.setSuffix("%")
        row.addWidget(self.cloud)
        layout.addWidget(self.cloud_group)
        self.cloud_group.hide()
        self.search_button = button("Search", self.search, True)
        self.search_button.setEnabled(False)
        layout.addWidget(self.search_button)
        layout.addStretch()

    def discover(self, *args):
        if not self.client:
            return
        self.discovery_id += 1
        generation = self.discovery_id
        self.collection.clear()
        self.search_button.setEnabled(False)
        self.clear_results()
        client, root = self.client, self.catalogue.currentText()

        def done(entries):
            if generation != self.discovery_id:
                return
            self.collection.blockSignals(True)
            for entry in entries:
                self.collection.addItem(entry["label"], entry)
            self.collection.blockSignals(False)
            self.collection_changed()
            self.status.setText(
                f"{len(entries)} collections in {root}." if entries else "No collections found. Refresh to retry."
            )

        self.submit("Discovering collections…", lambda: client.discover(root), done)

    def collection_changed(self, *args):
        entry = self.collection.currentData()
        self.search_button.setEnabled(bool(entry))
        self.cloud_group.hide()
        self.cloud.setValue(100)
        self.collection_description.setText((entry["collection"].get("description") or "")[:500] if entry else "")
        if entry and self.client:
            client = self.client

            def done(supported):
                if self.collection.currentData() == entry:
                    self.cloud_group.setVisible(supported)

            self.submit("Checking available filters…", lambda: client.cloud_supported(entry), done)

    def set_bbox(self, bbox):
        try:
            self.bbox = validate_bbox(bbox) if bbox is not None else None
        except ValueError as error:
            self.status.setText(str(error))
            return
        self.aoi_text.setText(", ".join(f"{x:.5f}" for x in self.bbox) if self.bbox else "No area of interest")
        self.commercial.invalidate()
        self.overlays.show_aoi(self.bbox, self.show_aoi.isChecked() and self.isVisible())

    def draw(self):
        if self.iface.mapCanvas().mapTool() != self.draw_tool:
            self.previous_tool = self.iface.mapCanvas().mapTool()
        self.iface.mapCanvas().setMapTool(self.draw_tool)
        self.status.setText("Drag a rectangle on the map to define your AOI.")

    def drawn(self, rect):
        try:
            self.set_bbox(self.overlays.extent_wgs84(rect))
        except Exception:
            self.status.setText("Could not transform the drawn AOI to WGS84.")
        if self.previous_tool:
            self.iface.mapCanvas().setMapTool(self.previous_tool)

    def map_extent(self):
        try:
            self.set_bbox(self.overlays.extent_wgs84(self.iface.mapCanvas().extent()))
        except Exception:
            self.status.setText("Could not transform the map extent to WGS84.")

    def import_aoi(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import AOI", "", "GeoJSON (*.geojson *.json)")
        if not path:
            return
        try:
            doc = json.loads(Path(path).read_text(encoding="utf-8-sig"))
            features = doc.get("features", [doc]) if doc.get("type") == "FeatureCollection" else [doc]
            geoms = [geometry(f.get("geometry", f)) for f in features]
            geoms = [g for g in geoms if g]
            if not geoms:
                raise ValueError("GeoJSON must contain valid Polygon or MultiPolygon geometries.")
            rect = geoms[0].boundingBox()
            for geom in geoms[1:]:
                rect.combineExtentWith(geom.boundingBox())
            self.set_bbox([rect.xMinimum(), rect.yMinimum(), rect.xMaximum(), rect.yMaximum()])
        except Exception as error:
            self.status.setText("Cannot import AOI: " + str(error))

    def build_results(self):
        _, layout = self.page("Results")
        self.timeline = Timeline()
        self.timeline.selected.connect(self.select_timeline)
        layout.addWidget(self.timeline)
        row = QtWidgets.QHBoxLayout()
        self.show_footprints = QtWidgets.QCheckBox("Show footprints")
        self.show_footprints.setChecked(True)
        self.show_footprints.toggled.connect(self.update_overlays)
        self.show_aoi = QtWidgets.QCheckBox("Show AOI")
        self.show_aoi.setChecked(True)
        self.show_aoi.toggled.connect(self.update_overlays)
        row.addWidget(self.show_footprints)
        row.addWidget(self.show_aoi)
        layout.addLayout(row)
        self.summary = label("Search for imagery to see results here.")
        layout.addWidget(self.summary)
        self.results = QtWidgets.QListWidget()
        self.results.setMinimumHeight(150)
        self.results.currentRowChanged.connect(self.select_result)
        self.results.itemDoubleClicked.connect(self.load_assets)
        layout.addWidget(self.results)
        row = QtWidgets.QHBoxLayout()
        self.previous = button("Previous", self.previous_page)
        self.next = button("Next", self.next_page)
        row.addWidget(self.previous)
        row.addWidget(self.next)
        row.addWidget(button("Clear results", self.clear_results))
        layout.addLayout(row)
        self.previous.setEnabled(False)
        self.next.setEnabled(False)
        self.thumbnail = QtWidgets.QLabel()
        self.thumbnail.setMaximumHeight(120)
        layout.addWidget(self.thumbnail)
        self.details = label("")
        layout.addWidget(self.details)
        layout.addWidget(button("Zoom to item", self.zoom_item))
        self.assets = QtWidgets.QListWidget()
        self.assets.setMaximumHeight(140)
        layout.addWidget(self.assets)
        layout.addWidget(button("Load Selected Assets", self.load_assets, True))
        self.commercial = CommercialPanel(self)
        self.commercial.hide()
        layout.addWidget(self.commercial)

    def clear_results(self):
        self.search_id += 1
        self.selection_id += 1
        self.items, self.history, self.next_link = [], [], None
        self.results.clear()
        self.timeline.set_items([])
        self.assets.clear()
        self.details.clear()
        self.thumbnail.clear()
        self.summary.setText("Search for imagery to see results here.")
        self.commercial.set_item(None)
        self.commercial.hide()
        self.previous.setEnabled(False)
        self.next.setEnabled(False)
        self.overlays.clear()

    def search(self):
        entry = self.collection.currentData()
        if not entry or not self.client:
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
            self.status.setText(str(error))
            return
        self.clear_results()
        self.search_params = params
        client, generation = self.client, self.search_id
        self.search_button.setEnabled(False)

        def done(page):
            self.search_button.setEnabled(True)
            if generation == self.search_id:
                self.display_page(page)
                self.tabs.setCurrentIndex(1)

        def failed(error):
            self.search_button.setEnabled(True)

        self.submit("Searching imagery…", lambda: client.request(entry["search"], "POST", params), done, failed)

    def display_page(self, page):
        self.current_page = page
        self.items = page.get("features", [])
        self.next_link = link(page, "next")
        self.results.blockSignals(True)
        self.results.clear()
        for item in self.items:
            self.results.addItem(
                f"{property_value(item, 'datetime', 'start_datetime')}\n{item.get('id', 'Untitled item')}"
            )
        self.results.blockSignals(False)
        total = (page.get("context") or {}).get(
            "matched", page.get("numberMatched", page.get("numMatched", len(self.items)))
        )
        self.summary.setText(
            f"{len(self.items)} items on this page • {total} matched"
            if self.items
            else "No imagery matched. Try a wider AOI or date range."
        )
        self.timeline.set_items(self.items)
        self.next.setEnabled(bool(self.next_link))
        self.previous.setEnabled(bool(self.history))
        self.results.setCurrentRow(0 if self.items else -1)
        if not self.items:
            self.select_result(-1)
        self.update_overlays()

    def next_page(self):
        if not self.next_link or not self.client:
            return
        client, entry, current, generation = self.client, dict(self.next_link), self.current_page, self.search_id
        self.next.setEnabled(False)

        def done(page):
            if generation == self.search_id:
                self.history.append(current)
                self.display_page(page)

        self.submit(
            "Loading next page…",
            lambda: client.page(entry, self.search_params, current.get("_url")),
            done,
            lambda error: self.next.setEnabled(bool(self.next_link)),
        )

    def previous_page(self):
        if self.history:
            self.search_id += 1
            self.display_page(self.history.pop())

    def select_timeline(self, index):
        self.results.setCurrentRow(index)
        self.results.scrollToItem(self.results.item(index))

    def select_result(self, index):
        self.selection_id += 1
        generation = self.selection_id
        self.assets.clear()
        self.thumbnail.clear()
        self.timeline.index = index
        self.timeline.update()
        self.commercial.hide()
        self.commercial.set_item(None)
        self.details.clear()
        if 0 <= index < len(self.items):
            item = self.items[index]
            values = [
                ("Item", item.get("id")),
                ("Collection", item.get("collection")),
                ("Acquired", property_value(item, "datetime", "start_datetime")),
                ("Resolution (m)", property_value(item, "gsd")),
                ("Cloud cover (%)", property_value(item, "eo:cloud_cover")),
                ("Locational accuracy (m)", property_value(item, "accuracy:geometric_rmse")),
                ("Licence", property_value(item, "license")),
            ]
            geom = geometry(item.get("geometry"))
            if geom and self.bbox:
                from qgis.core import QgsGeometry, QgsRectangle

                aoi = QgsGeometry.fromRect(QgsRectangle(*self.bbox))
                if aoi.area():
                    values.append(("AOI overlap", f"{100 * geom.intersection(aoi).area() / aoi.area():.1f}%"))
            self.details.setText("\n".join(f"{key}: {value or '—'}" for key, value in values))
            self.populate_assets(self.assets, item)
            commercial = "/catalogs/commercial/" in (href(item, "self") or "")
            self.commercial.setVisible(commercial)
            if commercial:
                self.commercial.set_item(item)
            thumb = next((a for a in item.get("assets", {}).values() if "thumbnail" in a.get("roles", [])), None)
            if thumb and self.client:
                client = self.client
                url = urljoin(href(item, "self") or client.base, thumb["href"])

                def done(data):
                    if generation == self.selection_id:
                        pixmap = QtGui.QPixmap()
                        if pixmap.loadFromData(data):
                            self.thumbnail.setPixmap(
                                pixmap.scaled(
                                    300,
                                    110,
                                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                    QtCore.Qt.TransformationMode.SmoothTransformation,
                                )
                            )

                self.submit("Loading thumbnail…", lambda: client.request(url, raw=True), done)
        self.update_overlays()

    def update_overlays(self, *args):
        self.overlays.footprints(
            self.items, self.results.currentRow(), self.show_footprints.isChecked() and self.isVisible()
        )
        self.overlays.show_aoi(self.bbox, self.show_aoi.isChecked() and self.isVisible())

    def zoom_item(self):
        index = self.results.currentRow()
        if 0 <= index < len(self.items):
            self.overlays.zoom(self.items[index])

    def populate_assets(self, widget, item, enabled=True):
        widget.clear()
        for key, asset in item.get("assets", {}).items():
            kind = asset_type(asset)
            row = QtWidgets.QListWidgetItem(f"{asset.get('title') or key} • {kind or asset.get('type') or 'File'}")
            row.setData(QtCore.Qt.ItemDataRole.UserRole, (key, asset))
            if kind and enabled:
                row.setFlags(row.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                row.setCheckState(QtCore.Qt.CheckState.Unchecked)
            else:
                row.setFlags(row.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)
            widget.addItem(row)

    def load_assets(self, *args):
        index = self.results.currentRow()
        if 0 <= index < len(self.items):
            self.load_selected(self.assets, self.items[index])

    def load_selected(self, widget, item):
        if not self.client or self.asset_busy:
            return
        selected = [
            widget.item(i).data(QtCore.Qt.ItemDataRole.UserRole)
            for i in range(widget.count())
            if widget.item(i).checkState() == QtCore.Qt.CheckState.Checked
        ]
        if not selected:
            self.status.setText("Select at least one supported COG, GeoTIFF or NetCDF asset.")
            return
        client = self.client
        self.asset_busy = True

        def work(task):
            import tempfile

            paths = []
            for key, asset in selected:
                if task.isCanceled():
                    raise HubError("Asset download cancelled.")
                url = urljoin(href(item, "self") or client.base, asset["href"])
                suffix = ".nc" if asset_type(asset) == "NetCDF" else ".tif"
                with tempfile.NamedTemporaryFile(prefix="eodh-", suffix=suffix, delete=False) as output:
                    path = output.name
                try:

                    def report(downloaded, total):
                        if task.isCanceled():
                            raise HubError("Asset download cancelled.")
                        task.download_progress.emit(key, downloaded, total)

                    client.request(url, destination=path, progress=report)
                except Exception:
                    Path(path).unlink(missing_ok=True)
                    raise
                paths.append((path, key))
            return paths

        def done(paths):
            self.asset_busy = False
            from eodh_qgis.layer_utils import get_netcdf_layers

            count = 0
            for path, key in paths:
                name = f"{item.get('id')}_{key}"
                layers = get_netcdf_layers(path, name) if path.endswith(".nc") else [QgsRasterLayer(path, name)]
                for layer in layers:
                    if layer.isValid():
                        QgsProject.instance().addMapLayer(layer)
                        count += 1
            self.status.setText(f"Loaded {count} layer(s)." if count else "No valid raster layers could be created.")

        def failed(error):
            self.asset_busy = False

        self.submit("Downloading selected assets…", work, done, failed, with_task=True)

    def build_workspace(self):
        _, layout = self.page("Workspace")
        layout.addWidget(label("Workspace commercial data"))
        layout.addWidget(
            label("Commercial records for your signed-in workspace. Completed orders can be loaded into the map.")
        )
        row = QtWidgets.QHBoxLayout()
        self.provider_filter = QtWidgets.QComboBox()
        self.provider_filter.addItem("All providers")
        self.status_filter = QtWidgets.QComboBox()
        self.status_filter.addItems(("All statuses", "Pending", "Processing", "Failed", "Completed"))
        for widget in (self.provider_filter, self.status_filter):
            widget.currentTextChanged.connect(self.filter_records)
            row.addWidget(widget)
        layout.addLayout(row)
        layout.addWidget(button("Refresh / Retry", self.refresh_records))
        self.orders = QtWidgets.QListWidget()
        self.orders.setMinimumHeight(200)
        self.orders.currentRowChanged.connect(self.select_record)
        layout.addWidget(self.orders)
        self.order_details = label("Refresh to retrieve commercial records.")
        layout.addWidget(self.order_details)
        self.order_assets = QtWidgets.QListWidget()
        self.order_assets.setMaximumHeight(150)
        layout.addWidget(self.order_assets)
        self.load_order = button("Load into map", self.load_record, True)
        self.load_order.setEnabled(False)
        layout.addWidget(self.load_order)
        layout.addStretch()
        self.tabs.currentChanged.connect(lambda index: self.refresh_records() if index == 2 and self.client else None)

    def refresh_records(self):
        if not self.client:
            return
        client = self.client
        self.order_details.setText("Loading commercial records…")

        def done(records):
            self.records = records
            selected = self.provider_filter.currentText()
            self.provider_filter.blockSignals(True)
            self.provider_filter.clear()
            self.provider_filter.addItems(["All providers", *sorted({r["_provider"] for r in records})])
            self.provider_filter.setCurrentText(selected)
            self.provider_filter.blockSignals(False)
            self.filter_records()

        def failed(error):
            self.records = []
            self.filter_records()
            self.order_details.setText(str(error) + "\nUse Refresh / Retry.")

        self.submit("Loading workspace commercial data…", client.records, done, failed)

    def filter_records(self, *args):
        self.orders.clear()
        p, s = self.provider_filter.currentText(), self.status_filter.currentText().lower()
        for item in self.records:
            status = record_status(item)
            category = "completed" if status in COMPLETED else status
            if p != "All providers" and item["_provider"] != p:
                continue
            if s != "all statuses" and category != s:
                continue
            row = QtWidgets.QListWidgetItem(f"{item['_provider']} • {status}\n{item.get('id')}")
            row.setData(QtCore.Qt.ItemDataRole.UserRole, item)
            self.orders.addItem(row)
        if self.orders.count():
            self.orders.setCurrentRow(0)
        else:
            self.order_details.setText("No commercial records match these filters.")
            self.order_assets.clear()
            self.load_order.setEnabled(False)

    def select_record(self, *args):
        row = self.orders.currentItem()
        self.order_assets.clear()
        self.load_order.setEnabled(False)
        if row:
            item = row.data(QtCore.Qt.ItemDataRole.UserRole)
            self.order_details.setText(
                "\n".join(
                    (
                        "Order: " + property_value(item, "order:id", "order_id", "orderId"),
                        "Status: " + record_status(item),
                        "Ordered: " + property_value(item, "order:date", "order_date", "ordered", "ordered_at"),
                        "Created: " + property_value(item, "created"),
                        "Updated: " + property_value(item, "updated"),
                        property_value(item, "order:message", "order_message", "failure_message", "message", "detail"),
                    )
                )
            )
            completed = record_status(item) in COMPLETED
            self.populate_assets(self.order_assets, item, completed)
            self.load_order.setEnabled(completed and any(asset_type(a) for a in item.get("assets", {}).values()))

    def load_record(self):
        row = self.orders.currentItem()
        if row:
            item = row.data(QtCore.Qt.ItemDataRole.UserRole)
            if record_status(item) in COMPLETED:
                self.load_selected(self.order_assets, item)

    def show_guide(self):
        path = Path(__file__).parents[1] / "USAGE_GUIDE.md"
        if not path.exists():
            path = Path(__file__).parents[2] / "USAGE_GUIDE.md"
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("EODH — Usage guide")
        dialog.resize(760, 650)
        layout = QtWidgets.QVBoxLayout(dialog)
        browser = QtWidgets.QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setMarkdown(
            path.read_text(encoding="utf-8") if path.exists() else "Usage guide unavailable in this installation."
        )
        layout.addWidget(browser)
        dialog.show()
        self.guide_dialog = dialog

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
