from qgis.core import Qgis, QgsMessageLog, QgsRasterLayer, QgsProject
from qgis.PyQt import QtCore, QtWidgets

from eodh_qgis.gui.v2.polygon_tool import PolygonCaptureTool

# Coordinate ranges (WGS84 degrees, EPSG:4326)
# Reference: https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md
LAT_MIN = -90.0
LAT_MAX = 90.0
LON_MIN = -180.0
LON_MAX = 180.0

# Default bounding box - UK (WGS84 degrees)
DEFAULT_BBOX_NORTH = 60.85
DEFAULT_BBOX_SOUTH = 49.9
DEFAULT_BBOX_WEST = -8.65
DEFAULT_BBOX_EAST = 1.77


class SearchWidget(QtWidgets.QWidget):
    def __init__(self, creds: dict[str, str], iface=None, parent=None):
        """Constructor."""
        super(SearchWidget, self).__init__(parent)
        self.creds = creds
        self.iface = iface
        self.catalog = None
        self.collection = None
        self.bbox = None
        self.polygon_tool = None
        self.search_results = []  # Store Item objects

        layout = QtWidgets.QVBoxLayout()

        # Row 1: Catalogue dropdown (read-only, synced from Overview)
        catalogue_layout = QtWidgets.QHBoxLayout()
        self.catalogue_dropdown = QtWidgets.QComboBox()
        self.catalogue_dropdown.addItem("Select a catalogue in Overview tab...")
        self.catalogue_dropdown.setEnabled(False)
        self.catalogue_dropdown.setMinimumWidth(300)
        catalogue_layout.addWidget(self.catalogue_dropdown)
        catalogue_layout.addStretch()
        layout.addLayout(catalogue_layout)

        layout.addSpacing(10)

        # Row 2: Date range filters
        filter_layout = QtWidgets.QHBoxLayout()
        filter_layout.addWidget(QtWidgets.QLabel("Date range"))
        two_months_ago = QtCore.QDate.currentDate().addMonths(-2)

        self.from_date = QtWidgets.QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(two_months_ago)
        self.from_date.setDisplayFormat("dd.MM.yyyy")
        filter_layout.addWidget(self.from_date)

        self.to_date = QtWidgets.QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(two_months_ago)
        self.to_date.setDisplayFormat("dd.MM.yyyy")
        filter_layout.addWidget(self.to_date)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        layout.addSpacing(10)

        # Spatial filter section
        self._setup_spatial_filter(layout)

        layout.addSpacing(10)

        # Row 3: Results list
        results_label = QtWidgets.QLabel("Search results")
        layout.addWidget(results_label)

        self.results_list = QtWidgets.QListWidget()
        self.results_list.setMinimumHeight(200)
        self.results_list.itemDoubleClicked.connect(self.on_result_double_clicked)
        layout.addWidget(self.results_list)

        # Row 4: Search button (right aligned)
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        self.search_button = QtWidgets.QPushButton("Search")
        self.search_button.clicked.connect(self.on_search_clicked)
        self.search_button.setEnabled(False)
        button_layout.addWidget(self.search_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _setup_spatial_filter(self, layout):
        """Setup the spatial filter UI with radio buttons and coordinate inputs."""
        spatial_label = QtWidgets.QLabel("Spatial range")
        layout.addWidget(spatial_label)

        # Radio buttons for input type
        radio_layout = QtWidgets.QHBoxLayout()
        self.direct_input_radio = QtWidgets.QRadioButton("Direct input")
        self.draw_map_radio = QtWidgets.QRadioButton("Draw on map")
        self.direct_input_radio.setChecked(True)
        self.direct_input_radio.toggled.connect(self._on_spatial_mode_changed)
        radio_layout.addWidget(self.direct_input_radio)
        radio_layout.addWidget(self.draw_map_radio)
        radio_layout.addStretch()
        layout.addLayout(radio_layout)

        # Coordinate input widget (compass-style layout)
        self.coord_widget = QtWidgets.QWidget()
        coord_layout = QtWidgets.QGridLayout(self.coord_widget)
        coord_layout.setContentsMargins(0, 0, 0, 0)

        # North (top center)
        north_layout = QtWidgets.QHBoxLayout()
        north_layout.addWidget(QtWidgets.QLabel("N"))
        self.north_input = QtWidgets.QDoubleSpinBox()
        self.north_input.setRange(LAT_MIN, LAT_MAX)
        self.north_input.setDecimals(2)
        self.north_input.setValue(DEFAULT_BBOX_NORTH)
        north_layout.addWidget(self.north_input)
        coord_layout.addLayout(north_layout, 0, 1, QtCore.Qt.AlignCenter)

        # West (middle left)
        west_layout = QtWidgets.QHBoxLayout()
        west_layout.addWidget(QtWidgets.QLabel("W"))
        self.west_input = QtWidgets.QDoubleSpinBox()
        self.west_input.setRange(LON_MIN, LON_MAX)
        self.west_input.setDecimals(2)
        self.west_input.setValue(DEFAULT_BBOX_WEST)
        west_layout.addWidget(self.west_input)
        coord_layout.addLayout(west_layout, 1, 0, QtCore.Qt.AlignRight)

        # East (middle right)
        east_layout = QtWidgets.QHBoxLayout()
        east_layout.addWidget(QtWidgets.QLabel("E"))
        self.east_input = QtWidgets.QDoubleSpinBox()
        self.east_input.setRange(LON_MIN, LON_MAX)
        self.east_input.setDecimals(2)
        self.east_input.setValue(DEFAULT_BBOX_EAST)
        east_layout.addWidget(self.east_input)
        coord_layout.addLayout(east_layout, 1, 2, QtCore.Qt.AlignLeft)

        # South (bottom center)
        south_layout = QtWidgets.QHBoxLayout()
        south_layout.addWidget(QtWidgets.QLabel("S"))
        self.south_input = QtWidgets.QDoubleSpinBox()
        self.south_input.setRange(LAT_MIN, LAT_MAX)
        self.south_input.setDecimals(2)
        self.south_input.setValue(DEFAULT_BBOX_SOUTH)
        south_layout.addWidget(self.south_input)
        coord_layout.addLayout(south_layout, 2, 1, QtCore.Qt.AlignCenter)

        layout.addWidget(self.coord_widget)

        # Draw on map widget
        self.draw_widget = QtWidgets.QWidget()
        draw_layout = QtWidgets.QHBoxLayout(self.draw_widget)
        draw_layout.setContentsMargins(0, 0, 0, 0)

        self.spatial_button = QtWidgets.QPushButton("Draw on map")
        self.spatial_button.setCheckable(True)
        self.spatial_button.clicked.connect(self.on_spatial_clicked)
        draw_layout.addWidget(self.spatial_button)

        self.clear_spatial_button = QtWidgets.QPushButton("Clear")
        self.clear_spatial_button.clicked.connect(self.on_clear_spatial)
        self.clear_spatial_button.setEnabled(False)
        draw_layout.addWidget(self.clear_spatial_button)

        draw_layout.addStretch()
        layout.addWidget(self.draw_widget)
        self.draw_widget.hide()  # Hidden by default (Direct input is selected)

    def _on_spatial_mode_changed(self, checked):
        """Handle switching between direct input and draw on map modes."""
        if self.direct_input_radio.isChecked():
            self.coord_widget.show()
            self.draw_widget.hide()
        else:
            self.coord_widget.hide()
            self.draw_widget.show()

    def _get_bbox(self):
        """Get the bounding box based on selected spatial mode.

        Returns:
            list: Bbox in format [west, south, east, north] or None if not available.
        """
        if self.direct_input_radio.isChecked():
            return [
                self.west_input.value(),
                self.south_input.value(),
                self.east_input.value(),
                self.north_input.value(),
            ]
        elif self.bbox:
            return [
                self.bbox.xMinimum(),
                self.bbox.yMinimum(),
                self.bbox.xMaximum(),
                self.bbox.yMaximum(),
            ]
        return None

    def set_catalog(self, catalog, catalog_name: str):
        """Receive catalog selection from Overview widget."""
        self.catalog = catalog
        self.collection = None  # Reset collection when catalog changes
        self.catalogue_dropdown.clear()
        self.catalogue_dropdown.addItem(catalog_name)
        self.search_button.setEnabled(False)  # Disable until collection is selected

    def set_collection(self, collection, collection_name: str):
        """Receive collection selection from Overview widget."""
        self.collection = collection
        self.search_button.setEnabled(True)

    def on_spatial_clicked(self):
        """Activate polygon drawing tool on the map canvas."""
        QgsMessageLog.logMessage("on_spatial_clicked called", "EODH", level=Qgis.Info)
        QgsMessageLog.logMessage(f"iface is: {self.iface}", "EODH", level=Qgis.Info)

        if not self.iface:
            QgsMessageLog.logMessage("iface is None!", "EODH", level=Qgis.Warning)
            QtWidgets.QMessageBox.warning(
                self, "Error", "Map canvas not available"
            )
            self.spatial_button.setChecked(False)
            return

        QgsMessageLog.logMessage("Creating PolygonCaptureTool", "EODH", level=Qgis.Info)
        self.polygon_tool = PolygonCaptureTool(self.iface.mapCanvas())
        self.polygon_tool.polygon_captured.connect(self.on_polygon_captured)
        self.iface.mapCanvas().setMapTool(self.polygon_tool)
        QgsMessageLog.logMessage("Map tool set", "EODH", level=Qgis.Info)

    def on_polygon_captured(self, geometry):
        """Handle polygon capture completion."""
        QgsMessageLog.logMessage("on_polygon_captured called", "EODH", level=Qgis.Info)
        self.bbox = geometry.boundingBox()
        QgsMessageLog.logMessage(f"bbox set to: {self.bbox.toString()}", "EODH", level=Qgis.Info)
        self.spatial_button.setChecked(False)
        self.clear_spatial_button.setEnabled(True)
        self.spatial_button.setText("Area selected")
        # Reset to default map tool
        if self.iface:
            self.iface.mapCanvas().unsetMapTool(self.polygon_tool)

    def on_clear_spatial(self):
        """Clear the spatial filter."""
        self.bbox = None
        self.clear_spatial_button.setEnabled(False)
        self.spatial_button.setText("Draw on map")
        if self.polygon_tool:
            self.polygon_tool.reset()

    def on_search_clicked(self):
        """Handle search button click."""
        if not self.catalog or not self.collection:
            return

        self.results_list.clear()
        self.search_button.setEnabled(False)
        self.search_button.setText("Searching...")

        try:
            start_date = self.from_date.date().toString("yyyy-MM-dd")
            end_date = self.to_date.date().toString("yyyy-MM-dd")

            # Get bbox based on selected mode
            bbox = self._get_bbox()
            if bbox is None:
                self.search_button.setEnabled(True)
                self.search_button.setText("Search")
                QtWidgets.QMessageBox.warning(
                    self, "Missing spatial filter", "Please draw a bounding box on the map."
                )
                return
            QgsMessageLog.logMessage(f"Using bbox: {bbox}", "EODH", level=Qgis.Info)

            results = self.catalog.search(
                limit=50,
                bbox=bbox,
                start_datetime=start_date,
                end_datetime=end_date,
                collections=[self.collection.id],
            )

            self.search_results = []
            for item in results:
                self.search_results.append(item)
                datetime_str = str(item.datetime)[:10] if item.datetime else "No date"
                self.results_list.addItem(f"{item.id} - {datetime_str}")

            if len(self.search_results) == 0:
                self.results_list.addItem("No results found.")

        except Exception as e:
            self.results_list.addItem(f"Error: {str(e)}")
        finally:
            self.search_button.setEnabled(True)
            self.search_button.setText("Search")

    def on_result_double_clicked(self, list_item):
        """Handle double-click on a search result to add it to the canvas."""
        row = self.results_list.row(list_item)
        if row < 0 or row >= len(self.search_results):
            return

        item = self.search_results[row]
        QgsMessageLog.logMessage(f"Double-clicked item: {item.id}", "EODH", level=Qgis.Info)

        # Log all available assets for debugging
        for key, a in item.assets.items():
            a_type = getattr(a, "type", "None")
            a_href = getattr(a, "href", "None")
            QgsMessageLog.logMessage(f"Asset '{key}': type={a_type}, href={a_href[:80]}...", "EODH", level=Qgis.Info)

        # Find best asset to load - prioritize by role/key
        asset = self._get_loadable_asset(item)
        if not asset:
            QgsMessageLog.logMessage(f"No loadable asset found for {item.id}", "EODH", level=Qgis.Warning)
            return

        url = asset.href
        asset_type = getattr(asset, "type", "") or ""

        # Use /vsicurl/ for COG and GeoTIFF assets (remote streaming)
        cog_types = [
            "image/tiff; application=geotiff; profile=cloud-optimized",
            "image/tiff; application=geotiff",
            "image/tiff",
        ]
        if any(cog_type in asset_type for cog_type in cog_types) or url.endswith(".tif") or url.endswith(".tiff"):
            url = f"/vsicurl/{url}"

        QgsMessageLog.logMessage(f"Loading asset: {url}", "EODH", level=Qgis.Info)
        layer = QgsRasterLayer(url, item.id)
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            QgsMessageLog.logMessage(f"Layer added: {item.id}", "EODH", level=Qgis.Info)
        else:
            QgsMessageLog.logMessage(f"Layer invalid: {layer.error().message()}", "EODH", level=Qgis.Warning)

    def _get_loadable_asset(self, item):
        """Find the best loadable asset from a STAC item.

        Based on qgis-stac-plugin pattern: check asset.type against known layer types.
        """
        # Known loadable types from qgis-stac-plugin
        loadable_types = [
            "image/tiff; application=geotiff; profile=cloud-optimized",  # COG
            "image/tiff; application=geotiff",  # GEOTIFF
            "application/x-netcdf",  # NETCDF
            "application/netcdf",
            "image/tiff",
            "image/png",
            "image/jpeg",
        ]

        # Priority order for asset keys
        priority_keys = ["visual", "data", "image", "B04", "B03", "B02", "red", "green", "blue", "quicklook"]

        def is_loadable(asset, asset_key=None):
            if not hasattr(asset, "href"):
                return False
            asset_type = getattr(asset, "type", None)
            # Check if asset type contains any loadable type (substring match like qgis-stac-plugin)
            if asset_type:
                for lt in loadable_types:
                    if lt in asset_type or asset_type in lt:
                        return True
            # Fallback: check file extension
            href = asset.href.lower()
            if href.endswith(".tif") or href.endswith(".tiff") or href.endswith(".nc"):
                return True
            if href.endswith(".png") or href.endswith(".jpg") or href.endswith(".jpeg"):
                return True
            # If type is None but it's a quicklook/data/visual asset, try it anyway
            if asset_type is None and asset_key in ["quicklook", "data", "visual", "image"]:
                return True
            return False

        # First try priority keys
        for key in priority_keys:
            if key in item.assets:
                asset = item.assets[key]
                if is_loadable(asset, key):
                    return asset

        # Fall back to first loadable asset (skip thumbnails)
        for asset_key, asset in item.assets.items():
            roles = getattr(asset, "roles", []) or []
            if "thumbnail" in roles or asset_key == "thumbnail":
                continue
            if is_loadable(asset, asset_key):
                return asset

        return None
