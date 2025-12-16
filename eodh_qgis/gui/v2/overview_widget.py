import pyeodh
from qgis.PyQt import QtCore, QtWidgets


class OverviewWidget(QtWidgets.QWidget):
    # Signal emitted when catalogue selection changes, passes (catalog, catalog_name)
    catalogue_changed = QtCore.pyqtSignal(object, str)
    # Signal emitted when collection selection changes, passes (collection, collection_name)
    collection_changed = QtCore.pyqtSignal(object, str)

    def __init__(self, creds: dict[str, str], parent=None):
        """Constructor."""
        super(OverviewWidget, self).__init__(parent)
        self.creds = creds
        self.catalog_service = None
        self.catalogs = {}  # Store catalog objects by index
        self.collections = {}  # Store collection objects by index
        self.selected_collection = None

        layout = QtWidgets.QVBoxLayout()

        # Catalogue dropdown section
        dropdown_layout = QtWidgets.QHBoxLayout()
        dropdown_layout.addStretch()
        self.catalogue_dropdown = QtWidgets.QComboBox()
        self.catalogue_dropdown.addItem("Select a catalogue...", None)
        self.catalogue_dropdown.setMinimumWidth(300)
        self.catalogue_dropdown.currentIndexChanged.connect(self.on_catalogue_changed)
        dropdown_layout.addWidget(self.catalogue_dropdown)
        dropdown_layout.addStretch()
        layout.addLayout(dropdown_layout)

        layout.addSpacing(10)

        # Collection dropdown section
        collection_layout = QtWidgets.QHBoxLayout()
        collection_layout.addStretch()
        self.collection_dropdown = QtWidgets.QComboBox()
        self.collection_dropdown.addItem("Select a catalogue first...", None)
        self.collection_dropdown.setMinimumWidth(300)
        self.collection_dropdown.setEnabled(False)
        self.collection_dropdown.currentIndexChanged.connect(self.on_collection_changed)
        collection_layout.addWidget(self.collection_dropdown)
        collection_layout.addStretch()
        layout.addLayout(collection_layout)

        layout.addSpacing(20)

        # Statistics grid
        stats_layout = QtWidgets.QGridLayout()

        # Number of items
        num_items_label = QtWidgets.QLabel("Number of items")
        num_items_label.setAlignment(QtCore.Qt.AlignCenter)
        self.num_items_value = QtWidgets.QLabel("-")
        self.num_items_value.setAlignment(QtCore.Qt.AlignCenter)
        self.num_items_value.setStyleSheet("font-size: 36px; font-weight: bold;")

        # Date range
        date_range_label = QtWidgets.QLabel("Date range")
        date_range_label.setAlignment(QtCore.Qt.AlignCenter)
        self.date_range_value = QtWidgets.QLabel("-")
        self.date_range_value.setAlignment(QtCore.Qt.AlignCenter)
        self.date_range_value.setStyleSheet("font-size: 18px;")

        # Item average size
        avg_size_label = QtWidgets.QLabel("Item average size (MB)")
        avg_size_label.setAlignment(QtCore.Qt.AlignCenter)
        self.avg_size_value = QtWidgets.QLabel("N/A")
        self.avg_size_value.setAlignment(QtCore.Qt.AlignCenter)
        self.avg_size_value.setStyleSheet("font-size: 36px; font-weight: bold;")

        # Total catalogue size
        total_size_label = QtWidgets.QLabel("Total catalogue size (GB)")
        total_size_label.setAlignment(QtCore.Qt.AlignCenter)
        self.total_size_value = QtWidgets.QLabel("N/A")
        self.total_size_value.setAlignment(QtCore.Qt.AlignCenter)
        self.total_size_value.setStyleSheet("font-size: 36px; font-weight: bold;")

        # Row 0: labels
        stats_layout.addWidget(num_items_label, 0, 0)
        stats_layout.addWidget(date_range_label, 0, 1)
        # Row 1: values
        stats_layout.addWidget(self.num_items_value, 1, 0)
        stats_layout.addWidget(self.date_range_value, 1, 1)
        # Row 2: labels
        stats_layout.addWidget(avg_size_label, 2, 0)
        stats_layout.addWidget(total_size_label, 2, 1)
        # Row 3: values
        stats_layout.addWidget(self.avg_size_value, 3, 0)
        stats_layout.addWidget(self.total_size_value, 3, 1)

        layout.addLayout(stats_layout)
        layout.addStretch()

        self.setLayout(layout)

        self._populate_catalogue_dropdown()

    def _populate_catalogue_dropdown(self):
        """Populate the dropdown with available catalogues."""
        try:
            self.catalog_service = pyeodh.Client(
                username=self.creds["username"
                ], token=self.creds["token"]
            ).get_catalog_service()

            catalogs = self.catalog_service.get_catalogs()
            for idx, cat in enumerate(catalogs):
                self.catalogs[idx + 1] = cat  # +1 because index 0 is "Select..."
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
            cat_name = self.catalogue_dropdown.currentText()

            # Emit signal for other widgets
            self.catalogue_changed.emit(catalog, cat_name)

            # Reset collection state
            self.collections = {}
            self.selected_collection = None
            self.collection_dropdown.clear()
            self.collection_dropdown.addItem("Select a collection...", None)

            collections = catalog.get_collections()

            # Populate collection dropdown
            for idx, collection in enumerate(collections):
                # Add to dropdown (idx + 1 because index 0 is "Select...")
                self.collections[idx + 1] = collection
                self.collection_dropdown.addItem(
                    collection.title or collection.id, idx + 1
                )

            # Reset statistics until a collection is selected
            self.num_items_value.setText("-")
            self.date_range_value.setText("-")

            # Enable collection dropdown
            self.collection_dropdown.setEnabled(True)

        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "Error", f"Failed to load catalogue statistics: {str(e)}"
            )

    def on_collection_changed(self, index):
        """Handle collection selection change."""
        col_idx = self.collection_dropdown.itemData(index)
        if not col_idx or col_idx not in self.collections:
            self.selected_collection = None
            self.num_items_value.setText("-")
            self.date_range_value.setText("-")
            return

        collection = self.collections[col_idx]
        col_name = self.collection_dropdown.currentText()
        self.selected_collection = collection

        # Emit signal for other widgets
        self.collection_changed.emit(collection, col_name)

        # Update statistics for selected collection
        try:
            total_items = 0
            min_date = None
            max_date = None

            items = collection.get_items()
            if items.total_count:
                total_items = items.total_count

            if hasattr(collection, "extent") and collection.extent:
                temporal = getattr(collection.extent, "temporal", None)
                if temporal and temporal.intervals:
                    for interval in temporal.intervals:
                        if interval[0] and (min_date is None or interval[0] < min_date):
                            min_date = interval[0]
                        if interval[1] and (max_date is None or interval[1] > max_date):
                            max_date = interval[1]

            # Update statistics
            self.num_items_value.setText(str(total_items) if total_items else "-")

            if min_date and max_date:
                min_str = min_date.strftime("%d.%m.%Y") if hasattr(min_date, "strftime") else str(min_date)[:10]
                max_str = max_date.strftime("%d.%m.%Y") if hasattr(max_date, "strftime") else str(max_date)[:10]
                self.date_range_value.setText(f"{min_str}  \u2192  {max_str}")
            else:
                self.date_range_value.setText("-")

        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "Error", f"Failed to load collection statistics: {str(e)}"
            )
