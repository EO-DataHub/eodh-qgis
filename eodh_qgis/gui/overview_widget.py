import os

import pyeodh
from pyeodh.resource_catalog import Catalog, CatalogService, Collection
from qgis.core import Qgis, QgsMessageLog
from qgis.PyQt import QtCore, QtGui, QtWidgets, uic

from eodh_qgis.gui.collection_details_dialog import CollectionDetailsDialog

# Load the UI file
FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/overview.ui")
)


class OverviewWidget(QtWidgets.QWidget, FORM_CLASS):
    # Signal emitted when catalogue selection changes, passes (catalog, catalog_name)
    catalogue_changed = QtCore.pyqtSignal(object, str)
    # Signal emitted when collection selection changes,
    # passes (collection, collection_name)
    collection_changed = QtCore.pyqtSignal(object, str)

    def __init__(self, creds: dict[str, str], parent=None):
        """Constructor."""
        super(OverviewWidget, self).__init__(parent)
        self.setupUi(self)

        self.creds = creds
        self.catalog_service: CatalogService | None = None
        self.catalogs: dict[int, Catalog] = {}  # Store catalog objects by index
        self.collections: dict[str, Collection] = {}  # Store collections by ID
        self.selected_collection: Collection | None = None
        self.selected_catalog: Catalog | None = None

        # Type hints for UI elements (from .ui file)
        self.catalogue_dropdown: QtWidgets.QComboBox
        self.filter_collections_input: QtWidgets.QLineEdit
        self.view_details_btn: QtWidgets.QPushButton
        self.collections_tree: QtWidgets.QTreeView
        self.collections_count_label: QtWidgets.QLabel
        self.selected_collection_label: QtWidgets.QLabel
        self.item_count_label: QtWidgets.QLabel

        # Setup collections tree model
        self._setup_collections_tree()

        # Initialize UI state
        self.catalogue_dropdown.addItem("Select a catalogue...", None)

        # Connect signals
        self.catalogue_dropdown.currentIndexChanged.connect(self.on_catalogue_changed)
        self.filter_collections_input.textChanged.connect(self.on_filter_text_changed)
        self.view_details_btn.clicked.connect(self.on_view_details_clicked)
        self.collections_tree.doubleClicked.connect(self.on_collection_double_clicked)

        self._populate_catalogue_dropdown()

    def _setup_collections_tree(self):
        """Initialize the tree view with a model and proxy for filtering."""
        # Create model with columns: Title, ID, Date Range, Spatial Extent
        self.collections_model = QtGui.QStandardItemModel()
        self.collections_model.setHorizontalHeaderLabels(
            ["Title", "ID", "Date Range", "Spatial Extent"]
        )

        # Create proxy model for filtering
        self.collections_proxy = QtCore.QSortFilterProxyModel()
        self.collections_proxy.setSourceModel(self.collections_model)
        self.collections_proxy.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.collections_proxy.setFilterKeyColumn(-1)  # Filter all columns

        # Set model on tree view
        self.collections_tree.setModel(self.collections_proxy)

        # Connect selection changed signal
        self.collections_tree.selectionModel().selectionChanged.connect(
            self.on_collection_selection_changed
        )

        # Configure tree view appearance - all columns manually resizable
        self.collections_tree.header().setStretchLastSection(True)
        self.collections_tree.header().setSectionResizeMode(
            QtWidgets.QHeaderView.Interactive
        )
        # Set reasonable default widths
        self.collections_tree.header().resizeSection(0, 250)  # Title
        self.collections_tree.header().resizeSection(1, 150)  # ID
        self.collections_tree.header().resizeSection(2, 180)  # Date Range

    def _populate_catalogue_dropdown(self):
        """Populate the dropdown with available catalogues."""
        try:
            self.catalog_service = pyeodh.Client(
                username=self.creds["username"], token=self.creds["token"]
            ).get_catalog_service()

            catalogs = self.catalog_service.get_catalogs()
            for idx, cat in enumerate(catalogs):
                self.catalogs[idx + 1] = cat  # +1 because index 0 is "Select..."

                if cat.title is None:
                    QgsMessageLog.logMessage(
                        f"Catalogue with ID {cat.id} has no title",
                        "EODH",
                        level=Qgis.Info,
                    )

                self.catalogue_dropdown.addItem(cat.title or cat.id, idx + 1)
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "Error", f"Failed to load catalogues: {str(e)}"
            )

    def on_catalogue_changed(self, index):
        """Handle catalogue selection change."""
        cat_idx = self.catalogue_dropdown.itemData(index)
        if not cat_idx or cat_idx not in self.catalogs:
            return

        try:
            catalog = self.catalogs[cat_idx]
            self.selected_catalog = catalog
            cat_name = self.catalogue_dropdown.currentText()

            # Emit signal for other widgets
            self.catalogue_changed.emit(catalog, cat_name)

            # Reset collection state
            self.collections = {}
            self.selected_collection = None
            self.collections_model.removeRows(0, self.collections_model.rowCount())
            self.selected_collection_label.setText("None")
            self.view_details_btn.setEnabled(False)

            # Fetch and populate collections
            collections = catalog.get_collections()
            collection_count = 0

            for collection in collections:
                collection_id = collection.id
                self.collections[collection_id] = collection

                # Create row items
                title_item = QtGui.QStandardItem(collection.title or collection.id)
                title_item.setData(collection_id, QtCore.Qt.UserRole)
                id_item = QtGui.QStandardItem(collection.id)

                # Extract temporal extent for date range
                date_range = self._get_temporal_extent(collection)
                date_range_item = QtGui.QStandardItem(date_range)

                # Extract spatial extent
                spatial_extent = self._get_spatial_extent(collection)
                spatial_extent_item = QtGui.QStandardItem(spatial_extent)

                self.collections_model.appendRow(
                    [title_item, id_item, date_range_item, spatial_extent_item]
                )
                collection_count += 1

            # Update count label
            self.collections_count_label.setText(f"{collection_count} collections")

            QgsMessageLog.logMessage(
                f"Loaded {collection_count} collections from {cat_name}",
                "EODH",
                level=Qgis.Info,
            )

        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "Error", f"Failed to load collections: {str(e)}"
            )

    def on_filter_text_changed(self, text):
        """Filter collections by title or ID."""
        self.collections_proxy.setFilterRegularExpression(text)

    def on_collection_selection_changed(self, selected, deselected):
        """Handle collection selection in tree view."""
        indexes = self.collections_tree.selectionModel().selectedRows()
        if not indexes:
            self.selected_collection = None
            self.selected_collection_label.setText("None")
            self.view_details_btn.setEnabled(False)
            return

        # Get the selected row's data
        proxy_index = indexes[0]
        source_index = self.collections_proxy.mapToSource(proxy_index)
        title_item = self.collections_model.item(source_index.row(), 0)
        collection_id = title_item.data(QtCore.Qt.UserRole)

        if collection_id not in self.collections:
            return

        collection = self.collections[collection_id]
        self.selected_collection = collection
        col_name = collection.title or collection.id

        # Update UI
        self.selected_collection_label.setText(col_name)
        self.view_details_btn.setEnabled(True)

        # Emit signal for other widgets (like Search tab)
        self.collection_changed.emit(collection, col_name)

    def on_collection_double_clicked(self, index):
        """Handle double-click on collection to show details."""
        self.on_view_details_clicked()

    def on_view_details_clicked(self):
        """Show collection details dialog."""
        if not self.selected_collection:
            return

        dialog = CollectionDetailsDialog(self.selected_collection, self)
        dialog.exec()

    def _get_temporal_extent(self, collection: Collection) -> str:
        """Extract temporal extent as a formatted date range string.

        Args:
            collection: Collection object from pyeodh

        Returns:
            Formatted date range string (e.g., "2020-01-01 to 2024-12-31")
        """
        extent = getattr(collection, "extent", None)
        if not extent:
            return "N/A"

        temporal = getattr(extent, "temporal", None)
        if not temporal or not hasattr(temporal, "intervals") or not temporal.intervals:
            return "N/A"

        interval = temporal.intervals[0]  # Use first interval
        if len(interval) < 2:
            return "N/A"

        from_date = interval[0]
        to_date = interval[1]

        # Format dates
        def format_date(dt):
            if dt is None:
                return "Open"
            if hasattr(dt, "strftime"):
                return dt.strftime("%Y-%m-%d")
            return str(dt)[:10]

        from_str = format_date(from_date)
        to_str = format_date(to_date)

        return f"{from_str} to {to_str}"

    def _get_spatial_extent(self, collection: Collection) -> str:
        """Extract spatial extent as a formatted bbox string.

        Args:
            collection: Collection object from pyeodh

        Returns:
            Formatted bbox string (e.g., "W: -10.5, S: 35.0, E: 5.5, N: 45.0")
        """
        extent = getattr(collection, "extent", None)
        if not extent:
            return "N/A"

        spatial = getattr(extent, "spatial", None)
        if not spatial or not hasattr(spatial, "bboxes") or not spatial.bboxes:
            return "N/A"

        bbox = spatial.bboxes[0]  # Use first bbox
        if len(bbox) < 4:
            return "N/A"

        west, south, east, north = bbox[0], bbox[1], bbox[2], bbox[3]
        return f"W:{west:.1f}, S:{south:.1f}, E:{east:.1f}, N:{north:.1f}"
