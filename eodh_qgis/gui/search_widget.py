from __future__ import annotations

import os
from functools import partial

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsMessageLog,
    QgsProject,
)
from qgis.gui import QgsProjectionSelectionDialog
from qgis.PyQt import QtCore, QtWidgets, uic

from eodh_qgis.asset_utils import (
    extract_epsg_from_asset,
    get_all_loadable_assets,
    get_asset_file_type,
)
from eodh_qgis.crs_utils import (
    apply_crs_to_layer,
    extract_epsg_from_item,
)
from eodh_qgis.geometry_utils import add_footprint_to_project, item_has_geometry
from eodh_qgis.gui import COMBOBOX_SCROLLABLE_STYLE
from eodh_qgis.gui.polygon_tool import PolygonCaptureTool
from eodh_qgis.gui.result_item_card import ResultItemCard
from eodh_qgis.gui.variable_selection_dialog import VariableSelectionDialog
from eodh_qgis.layer_loader import KerchunkFetchTask, LayerLoaderTask

# Load the UI file
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), "../ui/search.ui"))


class SearchWidget(QtWidgets.QWidget, FORM_CLASS):
    def __init__(self, iface=None, parent=None):
        """Constructor."""
        super().__init__(parent)
        self.setupUi(self)

        self.iface = iface
        self.catalog = None
        self.collection = None
        self.catalogue_collections = {}  # id -> Collection for dropdown
        self.bbox = None
        self.polygon_tool = None
        self.search_results = []  # Store Item objects

        # Pagination state
        self.page_size = 50
        self.current_page = 0
        self.total_results = 0
        self.paginated_results = None  # Store PaginatedList for lazy loading
        self.all_fetched_results = []  # Cache all fetched results

        # Footprint selection state (item.id -> item)
        self.selected_footprint_items = {}

        # Type hints for UI elements (from .ui file)
        self.catalogue_dropdown: QtWidgets.QComboBox
        self.collection_dropdown: QtWidgets.QComboBox
        self.from_date: QtWidgets.QDateEdit
        self.to_date: QtWidgets.QDateEdit
        self.north_input: QtWidgets.QDoubleSpinBox
        self.south_input: QtWidgets.QDoubleSpinBox
        self.east_input: QtWidgets.QDoubleSpinBox
        self.west_input: QtWidgets.QDoubleSpinBox
        self.draw_map_button: QtWidgets.QPushButton
        self.use_extent_button: QtWidgets.QPushButton
        self.results_scroll_area: QtWidgets.QScrollArea
        self.search_button: QtWidgets.QPushButton
        self.prev_page_btn: QtWidgets.QPushButton
        self.next_page_btn: QtWidgets.QPushButton
        self.page_label: QtWidgets.QLabel
        self.results_count_label: QtWidgets.QLabel
        self.add_selected_footprints_btn: QtWidgets.QPushButton
        self.add_all_footprints_btn: QtWidgets.QPushButton
        self.sort_field_combo: QtWidgets.QComboBox

        # Initialize UI state
        self.catalogue_dropdown.setStyleSheet(COMBOBOX_SCROLLABLE_STYLE)
        self.catalogue_dropdown.setMaxVisibleItems(20)
        self.collection_dropdown.setStyleSheet(COMBOBOX_SCROLLABLE_STYLE)
        self.collection_dropdown.setMaxVisibleItems(20)
        self.catalogue_dropdown.addItem("Select a catalogue in Overview tab...")
        self.collection_dropdown.addItem("All collections")

        # Set default dates (2 months ago)
        two_months_ago = QtCore.QDate.currentDate().addMonths(-2)
        self.from_date.setDate(two_months_ago)
        self.to_date.setDate(two_months_ago)

        # Configure draw map button with icon and tooltip
        self.draw_map_button.setIcon(QgsApplication.getThemeIcon("/mActionCapturePolygon.svg"))
        self.draw_map_button.setToolTip(
            "Draw bounding box on map\n\n"
            "Click to activate drawing mode, then:\n"
            "• Left-click on the map to add points\n"
            "• Right-click to finish and apply the bounding box\n\n"
            "The drawn polygon will be converted to a rectangular\n"
            "bounding box for the search area."
        )

        # Configure use extent button with icon and tooltip
        self.use_extent_button.setIcon(QgsApplication.getThemeIcon("/mActionZoomToArea.svg"))
        self.use_extent_button.setToolTip(
            "Use current map extent\n\n"
            "Sets the search bounding box to match the\n"
            "current visible area of the map canvas."
        )

        # Configure sort controls
        self.sort_field_combo.addItems(["Date (newest)", "Date (oldest)", "Item ID", "Collection"])

        # Connect signals
        self.search_button.clicked.connect(self.on_search_clicked)
        self.draw_map_button.clicked.connect(self.on_draw_map_clicked)
        self.collection_dropdown.currentIndexChanged.connect(self.on_collection_dropdown_changed)
        self.use_extent_button.clicked.connect(self.on_use_extent_clicked)
        self.prev_page_btn.clicked.connect(self.on_prev_page)
        self.next_page_btn.clicked.connect(self.on_next_page)
        self.add_selected_footprints_btn.clicked.connect(self._add_selected_footprints)
        self.add_all_footprints_btn.clicked.connect(self._add_all_footprints)
        self.sort_field_combo.currentIndexChanged.connect(self._on_sort_changed)

    def _get_bbox(self):
        """Get the bounding box from the coordinate inputs.

        Returns:
            list: Bbox in format [west, south, east, north].
        """
        return [
            self.west_input.value(),
            self.south_input.value(),
            self.east_input.value(),
            self.north_input.value(),
        ]

    def set_catalog(self, catalog, catalog_name: str):
        """Receive catalog selection from Overview widget."""
        self.catalog = catalog
        self.collection = None  # Reset collection when catalog changes
        self.catalogue_dropdown.clear()
        self.catalogue_dropdown.addItem(catalog_name)

        # Populate collection dropdown with all collections from catalogue
        self.collection_dropdown.blockSignals(True)  # Prevent signal during population
        self.collection_dropdown.clear()
        self.collection_dropdown.addItem("All collections", None)
        self.catalogue_collections = {}

        try:
            for coll in catalog.get_collections():
                self.catalogue_collections[coll.id] = coll
                display_name = coll.title or coll.id
                self.collection_dropdown.addItem(display_name, coll.id)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Failed to load collections for dropdown: {e!s}",
                "EODH",
                level=Qgis.Warning,
            )

        self.collection_dropdown.blockSignals(False)
        self.collection_dropdown.setEnabled(True)
        self.search_button.setEnabled(True)  # Enable search for catalogue-wide search

    def set_collection(self, collection, collection_name: str):
        """Receive collection selection from Overview widget."""
        self.collection = collection
        # Find and select in dropdown instead of replacing
        self.collection_dropdown.blockSignals(True)
        for i in range(self.collection_dropdown.count()):
            if self.collection_dropdown.itemData(i) == collection.id:
                self.collection_dropdown.setCurrentIndex(i)
                break
        self.collection_dropdown.blockSignals(False)
        self.search_button.setEnabled(True)

    def on_collection_dropdown_changed(self, index):
        """Handle collection dropdown selection change."""
        collection_id = self.collection_dropdown.itemData(index)
        if collection_id is None:
            self.collection = None
        else:
            self.collection = self.catalogue_collections.get(collection_id)

    def on_draw_map_clicked(self):
        """Activate polygon drawing tool on the map canvas."""
        QgsMessageLog.logMessage("on_draw_map_clicked called", "EODH", level=Qgis.Info)

        if not self.iface:
            QgsMessageLog.logMessage("iface is None!", "EODH", level=Qgis.Warning)
            QtWidgets.QMessageBox.warning(self, "Error", "Map canvas not available")
            self.draw_map_button.setChecked(False)
            return

        QgsMessageLog.logMessage("Creating PolygonCaptureTool", "EODH", level=Qgis.Info)
        self.polygon_tool = PolygonCaptureTool(self.iface.mapCanvas())
        self.polygon_tool.polygon_captured.connect(self.on_polygon_captured)
        self.iface.mapCanvas().setMapTool(self.polygon_tool)
        QgsMessageLog.logMessage("Map tool set", "EODH", level=Qgis.Info)

    def on_use_extent_clicked(self):
        """Use the current map canvas extent as the bounding box."""
        if not self.iface:
            QtWidgets.QMessageBox.warning(self, "Error", "Map canvas not available")
            return

        # Get current map canvas extent
        extent = self.iface.mapCanvas().extent()

        # Transform from project CRS to WGS84 (EPSG:4326)
        project_crs = QgsProject.instance().crs()
        wgs84_crs = QgsCoordinateReferenceSystem("EPSG:4326")

        if project_crs != wgs84_crs:
            transformer = QgsCoordinateTransform(project_crs, wgs84_crs, QgsProject.instance())
            extent = transformer.transformBoundingBox(extent)

        # Populate the coordinate inputs
        self.north_input.setValue(extent.yMaximum())
        self.south_input.setValue(extent.yMinimum())
        self.east_input.setValue(extent.xMaximum())
        self.west_input.setValue(extent.xMinimum())

        QgsMessageLog.logMessage(f"Extent set from map canvas: {extent.toString()}", "EODH", level=Qgis.Info)

    def on_polygon_captured(self, geometry):
        """Handle polygon capture completion.

        Populate N/W/E/S inputs from drawn bbox.
        """
        QgsMessageLog.logMessage("on_polygon_captured called", "EODH", level=Qgis.Info)

        # Transform geometry from project CRS to WGS84 (EPSG:4326)
        project_crs = QgsProject.instance().crs()
        wgs84_crs = QgsCoordinateReferenceSystem("EPSG:4326")

        if project_crs != wgs84_crs:
            transformer = QgsCoordinateTransform(project_crs, wgs84_crs, QgsProject.instance())
            geometry.transform(transformer)

        bbox = geometry.boundingBox()
        QgsMessageLog.logMessage(f"bbox set to: {bbox.toString()}", "EODH", level=Qgis.Info)

        # Populate the coordinate inputs with the transformed bbox
        self.north_input.setValue(bbox.yMaximum())
        self.south_input.setValue(bbox.yMinimum())
        self.east_input.setValue(bbox.xMaximum())
        self.west_input.setValue(bbox.xMinimum())

        self.draw_map_button.setChecked(False)

        # Reset to default map tool
        if self.iface:
            self.iface.mapCanvas().unsetMapTool(self.polygon_tool)

    def _show_asset_selection_dialog(
        self, loadable_assets: list[tuple[str, object]], item_id: str
    ) -> list[tuple[str, object]]:
        """Show dialog for user to select which assets to load.

        Returns list of selected (asset_key, asset) tuples.
        """
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(f"Select Assets to Load - {item_id}")
        dialog.setMinimumWidth(400)

        layout = QtWidgets.QVBoxLayout(dialog)

        # Info label
        layout.addWidget(QtWidgets.QLabel(f"Found {len(loadable_assets)} loadable assets. Select which to load:"))

        # Checkboxes for each asset
        checkboxes = []
        for asset_key, asset in loadable_assets:
            file_type = get_asset_file_type(asset)
            epsg = extract_epsg_from_asset(asset)

            label = f"{asset_key} ({file_type})"
            if epsg:
                label += f" - EPSG:{epsg}"

            checkbox = QtWidgets.QCheckBox(label)
            checkbox.setChecked(True)  # Default to selected
            checkboxes.append((checkbox, asset_key, asset))
            layout.addWidget(checkbox)

        # Select All / Deselect All buttons
        btn_layout = QtWidgets.QHBoxLayout()
        select_all_btn = QtWidgets.QPushButton("Select All")
        deselect_all_btn = QtWidgets.QPushButton("Deselect All")
        select_all_btn.clicked.connect(lambda: [cb[0].setChecked(True) for cb in checkboxes])
        deselect_all_btn.clicked.connect(lambda: [cb[0].setChecked(False) for cb in checkboxes])
        btn_layout.addWidget(select_all_btn)
        btn_layout.addWidget(deselect_all_btn)
        layout.addLayout(btn_layout)

        # OK / Cancel buttons
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec() == QtWidgets.QDialog.Accepted:
            return [(key, asset) for cb, key, asset in checkboxes if cb.isChecked()]
        return []

    def _populate_results_cards(self):
        """Populate the scroll area with result cards."""
        # Create new container widget with vertical layout
        scroll_container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(scroll_container)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        # Determine if we should show collection (when searching whole catalogue)
        show_collection = self.collection is None

        for item in self.search_results:
            card = ResultItemCard(
                item=item,
                parent_widget=self,
                show_collection=show_collection,
                parent=scroll_container,
            )
            # Connect the card's signals
            card.load_assets_requested.connect(self._load_item_assets)
            card.footprint_toggled.connect(self._on_footprint_toggled)
            layout.addWidget(card)
            layout.setAlignment(card, QtCore.Qt.AlignTop)

        # Add vertical spacer at the bottom
        spacer = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        layout.addItem(spacer)

        # Set the container as the scroll area's widget
        self.results_scroll_area.setWidget(scroll_container)

    def _clear_results(self):
        """Clear all result cards from the scroll area."""
        empty_widget = QtWidgets.QWidget()
        self.results_scroll_area.setWidget(empty_widget)

    def _show_no_results_message(self, message: str):
        """Display a message when no results are available."""
        scroll_container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(scroll_container)

        label = QtWidgets.QLabel(message)
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setStyleSheet("color: #666; font-size: 14px; padding: 20px;")

        layout.addWidget(label)
        layout.addStretch()

        self.results_scroll_area.setWidget(scroll_container)

    def _load_item_assets(self, item):
        """Load all loadable assets from a STAC item using background tasks.

        This method is called when double-clicking a card or clicking Load Assets.
        Uses QgsTask to prevent UI freeze during NetCDF downloads.
        """
        QgsMessageLog.logMessage(f"Loading assets for item: {item.id}", "EODH", level=Qgis.Info)

        # Get ALL loadable assets
        loadable_assets = get_all_loadable_assets(item)
        if not loadable_assets:
            QgsMessageLog.logMessage(f"No loadable assets found for {item.id}", "EODH", level=Qgis.Warning)
            return

        # Show selection dialog if multiple assets
        if len(loadable_assets) > 1:
            loadable_assets = self._show_asset_selection_dialog(loadable_assets, item.id)
            if not loadable_assets:
                return  # User cancelled or selected nothing

        asset_keys = [k for k, _ in loadable_assets]
        QgsMessageLog.logMessage(
            f"Loading {len(loadable_assets)} selected assets: {asset_keys}",
            "EODH",
            level=Qgis.Info,
        )

        # Extract item-level CRS (fast, no network call)
        item_epsg = extract_epsg_from_item(item)

        for asset_key, asset in loadable_assets:
            # Check if this is a NetCDF file
            file_type = get_asset_file_type(asset)

            if file_type == "NetCDF":
                # Fetch kerchunk in background, then show variable dialog on completion
                self._start_netcdf_load(item, asset_key, asset, item_epsg)
            else:
                # Non-NetCDF: start layer loading directly
                self._start_layer_load(item, asset_key, asset, None, item_epsg)

    def _start_layer_load(self, item, asset_key, asset, selected_variables, item_epsg):
        """Start a background layer loading task."""
        task = LayerLoaderTask(item, asset_key, asset, selected_variables)
        on_complete = partial(self._on_task_completed, task, asset, item_epsg, item)
        task.taskCompleted.connect(on_complete)
        task.taskTerminated.connect(self._on_task_terminated)
        QgsApplication.taskManager().addTask(task)

    def _start_netcdf_load(self, item, asset_key, asset, item_epsg):
        """Start NetCDF loading with background kerchunk fetch.

        Fetches kerchunk reference in background, shows variable selection
        dialog on completion, then starts the actual layer loading task.
        """
        task = KerchunkFetchTask(item)
        on_complete = partial(self._on_kerchunk_fetched, task, item, asset_key, asset, item_epsg)
        task.taskCompleted.connect(on_complete)
        task.taskTerminated.connect(self._on_task_terminated)
        QgsApplication.taskManager().addTask(task)

    def _on_kerchunk_fetched(self, task, item, asset_key, asset, item_epsg):
        """Handle kerchunk fetch completion — show variable dialog if needed."""
        selected_variables = None

        if task.variables:
            if len(task.variables) == 1:
                selected_variables = [task.variables[0].name]
            else:
                dialog = VariableSelectionDialog(task.variables, item.id, asset_key, self)
                if dialog.exec() == QtWidgets.QDialog.Accepted:
                    selected_variables = dialog.get_selected_variables()
                else:
                    return  # User cancelled

        self._start_layer_load(item, asset_key, asset, selected_variables, item_epsg)

    def _on_task_completed(self, task, asset, item_epsg, item):
        """Handle background task completion - add layers to project.

        Args:
            task: The completed LayerLoaderTask
            asset: The STAC asset object (for CRS extraction)
            item_epsg: Pre-fetched EPSG from item
            item: STAC item object (for lazy metadata XML fetch if needed)
        """
        if not task.layers:
            if task.error:
                QgsMessageLog.logMessage(f"Task failed: {task.error}", "EODH", level=Qgis.Warning)
            return

        layers_added = 0
        layers_needing_crs = []

        for layer in task.layers:
            # Try to apply CRS using priority order
            # Metadata XML is fetched lazily only if layer/asset/item CRS not found
            crs_applied = apply_crs_to_layer(layer, asset, item_epsg, item=item)

            if crs_applied:
                QgsProject.instance().addMapLayer(layer)
                layers_added += 1
            else:
                layers_needing_crs.append(layer)

        # Show CRS dialog for layers that need it
        if layers_needing_crs:
            QgsMessageLog.logMessage(
                f"[CRS] {len(layers_needing_crs)} layer(s) need CRS selection",
                "EODH",
                level=Qgis.Info,
            )
            dialog = QgsProjectionSelectionDialog(self)
            dialog.setWindowTitle(f"Select CRS for {len(layers_needing_crs)} layer(s)")
            if dialog.exec():
                user_crs = dialog.crs()
                QgsMessageLog.logMessage(
                    f"[CRS] User selected CRS: {user_crs.authid()}",
                    "EODH",
                    level=Qgis.Info,
                )
                for layer in layers_needing_crs:
                    layer.setCrs(user_crs)
                    QgsProject.instance().addMapLayer(layer)
                    layers_added += 1
            else:
                count = len(layers_needing_crs)
                QgsMessageLog.logMessage(
                    f"[CRS] User cancelled CRS selection, {count} layers not added",
                    "EODH",
                    level=Qgis.Warning,
                )

        QgsMessageLog.logMessage(
            f"Added {layers_added} layer(s) from background task",
            "EODH",
            level=Qgis.Info,
        )

    def _on_task_terminated(self):
        """Handle background task termination (cancelled or error)."""
        QgsMessageLog.logMessage("Layer loading task was terminated", "EODH", level=Qgis.Warning)

    def on_search_clicked(self):
        """Handle search button click."""
        if not self.catalog:
            return

        self._clear_results()
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
                    self,
                    "Missing spatial filter",
                    "Please draw a bounding box on the map.",
                )
                return
            QgsMessageLog.logMessage(f"Using bbox: {bbox}", "EODH", level=Qgis.Info)

            # Build search parameters
            search_params = {
                "limit": self.page_size,
                "bbox": bbox,
                "start_datetime": start_date,
                "end_datetime": end_date,
            }

            # Only filter by collection if one is selected
            if self.collection:
                search_params["collections"] = [self.collection.id]

            # Reset pagination state
            self.current_page = 0
            self.all_fetched_results = []

            # Get paginated results
            self.paginated_results = self.catalog.search(**search_params)

            # Get total count (this makes a separate API call)
            try:
                self.total_results = self.paginated_results.total_count
            except Exception:
                # If total_count fails, set to 0 and we'll update as we fetch
                self.total_results = 0

            # Clear footprint selections for new search
            self.selected_footprint_items.clear()

            # Fetch and display first page
            self._fetch_current_page()
            self._sort_results()
            self._populate_results_cards()
            self._update_pagination_controls()
            self._update_footprint_buttons()

            if len(self.search_results) == 0:
                self._show_no_results_message("No results found.")

        except Exception as e:
            self._show_no_results_message(f"Error: {e!s}")
            # Reset pagination on error
            self.total_results = 0
            self._update_pagination_controls()
        finally:
            self.search_button.setEnabled(True)
            self.search_button.setText("Search")

    def _fetch_current_page(self):
        """Fetch results for the current page and cache them."""
        if self.paginated_results is None:
            self.search_results = []
            return

        # Early return if no results to fetch
        if self.total_results == 0:
            self.search_results = []
            return

        start_idx = self.current_page * self.page_size
        end_idx = start_idx + self.page_size

        # Check if we already have these results cached
        if end_idx <= len(self.all_fetched_results):
            self.search_results = self.all_fetched_results[start_idx:end_idx]
            return

        # Fetch more results using slicing on PaginatedList
        try:
            # Fetch up to end_idx and cache
            new_results = list(self.paginated_results[:end_idx])
            self.all_fetched_results = new_results

            # Update total if we got fewer results than expected
            if len(new_results) < end_idx and not self.total_results:
                self.total_results = len(new_results)

            self.search_results = self.all_fetched_results[start_idx:end_idx]
        except IndexError:
            # No results available (pyeodh raises IndexError on empty results)
            self.search_results = []
            self.all_fetched_results = []
            self.total_results = 0
        except Exception as e:
            QgsMessageLog.logMessage(f"Error fetching page: {e!s}", "EODH", level=Qgis.Warning)
            self.search_results = []

    def _update_pagination_controls(self):
        """Update pagination buttons and labels based on current state."""
        if self.total_results == 0:
            self.page_label.setText("Page 0 of 0")
            self.results_count_label.setText("0 results")
            self.prev_page_btn.setEnabled(False)
            self.next_page_btn.setEnabled(False)
            return

        total_pages = max(1, (self.total_results + self.page_size - 1) // self.page_size)
        current_page_display = self.current_page + 1

        self.page_label.setText(f"Page {current_page_display} of {total_pages}")

        # Calculate result range for display
        start = self.current_page * self.page_size + 1
        end = min(start + len(self.search_results) - 1, self.total_results)
        self.results_count_label.setText(f"Showing {start}-{end} of {self.total_results}")

        # Enable/disable navigation buttons
        self.prev_page_btn.setEnabled(self.current_page > 0)
        self.next_page_btn.setEnabled(current_page_display < total_pages)

    def on_prev_page(self):
        """Navigate to the previous page of results."""
        if self.current_page > 0:
            self.current_page -= 1
            self._fetch_current_page()
            self._sort_results()
            self._populate_results_cards()
            self._update_pagination_controls()
            self._update_footprint_buttons()

    def on_next_page(self):
        """Navigate to the next page of results."""
        total_pages = max(1, (self.total_results + self.page_size - 1) // self.page_size)
        if self.current_page + 1 < total_pages:
            self.current_page += 1
            self._fetch_current_page()
            self._sort_results()
            self._populate_results_cards()
            self._update_pagination_controls()
            self._update_footprint_buttons()

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
        priority_keys = [
            "visual",
            "data",
            "image",
            "B04",
            "B03",
            "B02",
            "red",
            "green",
            "blue",
            "quicklook",
        ]

        def is_loadable(asset, asset_key=None):
            if not hasattr(asset, "href"):
                return False
            asset_type = getattr(asset, "type", None)
            # Check if asset type contains any loadable type (substring match)
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
            if asset_type is None and asset_key in [
                "quicklook",
                "data",
                "visual",
                "image",
            ]:
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

    def _on_footprint_toggled(self, item, checked):
        """Handle footprint checkbox toggle on a result card.

        Args:
            item: STAC item object
            checked: Whether checkbox is checked
        """
        if checked:
            self.selected_footprint_items[item.id] = item
        else:
            self.selected_footprint_items.pop(item.id, None)

        self._update_footprint_buttons()

    def _update_footprint_buttons(self):
        """Update footprint button text and enabled state."""
        count = len(self.selected_footprint_items)
        self.add_selected_footprints_btn.setText(f"Add Selected Footprints ({count})")
        self.add_selected_footprints_btn.setEnabled(count > 0)

        # Enable "Add All" if we have any results with geometry
        has_results_with_geometry = any(item_has_geometry(item) for item in self.search_results)
        self.add_all_footprints_btn.setEnabled(has_results_with_geometry)

    def _add_selected_footprints(self):
        """Add footprints of all selected items to the map."""
        if not self.selected_footprint_items:
            return

        added_count = 0
        for item in self.selected_footprint_items.values():
            if self._add_footprint_layer(item):
                added_count += 1

        QgsMessageLog.logMessage(f"Added {added_count} footprint layer(s) to map", "EODH", level=Qgis.Info)

        # Clear selections after adding
        self.selected_footprint_items.clear()
        self._update_footprint_buttons()

        # Uncheck all footprint checkboxes in the current cards
        scroll_widget = self.results_scroll_area.widget()
        if scroll_widget:
            for card in scroll_widget.findChildren(ResultItemCard):
                card.footprint_checkbox.setChecked(False)

    def _add_all_footprints(self):
        """Add footprints of all items on current page to the map."""
        if not self.search_results:
            return

        added_count = 0
        for item in self.search_results:
            if self._add_footprint_layer(item):
                added_count += 1

        QgsMessageLog.logMessage(f"Added {added_count} footprint layer(s) to map", "EODH", level=Qgis.Info)

    def _add_footprint_layer(self, item):
        """Add a single item's footprint as a vector layer.

        Args:
            item: STAC item object with geometry

        Returns:
            bool: True if layer was added successfully
        """
        return add_footprint_to_project(item)

    def _on_sort_changed(self):
        """Handle sort field or order change - re-sort and refresh display."""
        if not self.search_results:
            return

        self._sort_results()
        self._populate_results_cards()
        self._update_footprint_buttons()

    def _sort_results(self):
        """Sort search_results based on current sort settings."""
        sort_option = self.sort_field_combo.currentText()

        def get_datetime(item):
            """Get datetime for sorting, with fallback for None."""
            dt = getattr(item, "datetime", None)
            if dt is None:
                return ""
            return str(dt)

        def get_id(item):
            """Get item ID for sorting."""
            return str(getattr(item, "id", ""))

        def get_collection(item):
            """Get collection name for sorting."""
            return str(getattr(item, "collection", "") or "")

        if sort_option == "Date (newest)":
            self.search_results.sort(key=get_datetime, reverse=True)
        elif sort_option == "Date (oldest)":
            self.search_results.sort(key=get_datetime, reverse=False)
        elif sort_option == "Item ID":
            self.search_results.sort(key=get_id)
        elif sort_option == "Collection":
            self.search_results.sort(key=get_collection)
