from qgis.core import Qgis, QgsMessageLog
from qgis.PyQt import QtCore, QtWidgets

from eodh_qgis.gui.v2.polygon_tool import PolygonCaptureTool


class SearchWidget(QtWidgets.QWidget):
    def __init__(self, creds: dict[str, str], iface=None, parent=None):
        """Constructor."""
        super(SearchWidget, self).__init__(parent)
        self.creds = creds
        self.iface = iface
        self.catalog = None
        self.bbox = None
        self.polygon_tool = None

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

        filter_layout.addSpacing(20)

        # Spatial range buttons
        filter_layout.addWidget(QtWidgets.QLabel("Spatial range"))
        self.spatial_button = QtWidgets.QPushButton("Draw on map")
        self.spatial_button.setCheckable(True)
        self.spatial_button.clicked.connect(self.on_spatial_clicked)
        filter_layout.addWidget(self.spatial_button)

        self.clear_spatial_button = QtWidgets.QPushButton("Clear")
        self.clear_spatial_button.clicked.connect(self.on_clear_spatial)
        self.clear_spatial_button.setEnabled(False)
        filter_layout.addWidget(self.clear_spatial_button)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        layout.addSpacing(10)

        # Row 3: Results list
        results_label = QtWidgets.QLabel("Search results")
        layout.addWidget(results_label)

        self.results_list = QtWidgets.QListWidget()
        self.results_list.setMinimumHeight(200)
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

    def set_catalog(self, catalog, catalog_name: str):
        """Receive catalog selection from Overview widget."""
        self.catalog = catalog
        self.catalogue_dropdown.clear()
        self.catalogue_dropdown.addItem(catalog_name)
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
        if not self.catalog:
            return

        self.results_list.clear()
        self.search_button.setEnabled(False)
        self.search_button.setText("Searching...")

        try:
            start_date = self.from_date.date().toString("yyyy-MM-dd")
            end_date = self.to_date.date().toString("yyyy-MM-dd")

            # Use drawn bbox or default world bbox
            if self.bbox:
                bbox = [
                    self.bbox.xMinimum(),
                    self.bbox.yMinimum(),
                    self.bbox.xMaximum(),
                    self.bbox.yMaximum(),
                ]
                QgsMessageLog.logMessage(f"Using drawn bbox: {bbox}", "EODH", level=Qgis.Info)
            else:
                bbox = [-180, -90, 180, 90]
                QgsMessageLog.logMessage("Using default world bbox", "EODH", level=Qgis.Info)

            results = self.catalog.search(
                limit=50,
                bbox=bbox,
                start_datetime=start_date,
                end_datetime=end_date,
            )

            count = 0
            for item in results:
                count += 1
                datetime_str = str(item.datetime)[:10] if item.datetime else "No date"
                self.results_list.addItem(f"{item.id} - {datetime_str}")

            if count == 0:
                self.results_list.addItem("No results found.")

        except Exception as e:
            self.results_list.addItem(f"Error: {str(e)}")
        finally:
            self.search_button.setEnabled(True)
            self.search_button.setText("Search")
