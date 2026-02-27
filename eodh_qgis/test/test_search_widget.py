import unittest
from unittest.mock import MagicMock, patch

from qgis.core import QgsCoordinateReferenceSystem, QgsGeometry, QgsPointXY, QgsProject
from qgis.PyQt import QtCore, QtWidgets

from eodh_qgis.gui.search_widget import SearchWidget
from eodh_qgis.test.utilities import get_qgis_app


class TestSearchWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.QGIS_APP = get_qgis_app()
        assert cls.QGIS_APP is not None

    def setUp(self):
        self.mock_iface = MagicMock()
        self.mock_canvas = MagicMock()
        self.mock_iface.mapCanvas.return_value = self.mock_canvas
        self.widget = SearchWidget(iface=self.mock_iface, parent=None)

    def tearDown(self):
        self.widget = None

    def test_spatial_range_bbox_sent_in_search(self):
        """Test that N/W/E/S input values are sent as bbox in search request."""
        # Set up mock catalog and collection
        mock_catalog = MagicMock()
        mock_collection = MagicMock()
        mock_collection.id = "test_collection"
        mock_catalog.search.return_value = []  # Empty results

        # Use widget without iface for this test
        widget = SearchWidget(iface=None, parent=None)
        widget.catalog = mock_catalog
        widget.collection = mock_collection

        # Set spatial range values (N, S, E, W)
        widget.north_input.setValue(55.0)
        widget.south_input.setValue(50.0)
        widget.east_input.setValue(2.0)
        widget.west_input.setValue(-5.0)

        # Trigger search
        widget.on_search_clicked()

        # Assert catalog.search was called with correct bbox
        mock_catalog.search.assert_called_once()
        call_kwargs = mock_catalog.search.call_args.kwargs

        # bbox format is [west, south, east, north]
        expected_bbox = [-5.0, 50.0, 2.0, 55.0]
        self.assertEqual(call_kwargs["bbox"], expected_bbox)

    @patch("eodh_qgis.gui.search_widget.PolygonCaptureTool")
    def test_draw_on_canvas_activates_polygon_tool(self, mock_polygon_tool_class):
        """Test that clicking draw button activates the polygon capture tool."""
        mock_tool_instance = MagicMock()
        mock_polygon_tool_class.return_value = mock_tool_instance

        # Click the draw map button
        self.widget.on_draw_map_clicked()

        # Verify polygon tool was created with the canvas
        mock_polygon_tool_class.assert_called_once_with(self.mock_canvas)

        # Verify polygon_captured signal was connected
        mock_tool_instance.polygon_captured.connect.assert_called_once()

        # Verify tool was set on the canvas
        self.mock_canvas.setMapTool.assert_called_once_with(mock_tool_instance)

    def test_polygon_captured_populates_bbox_inputs(self):
        """Test that when a polygon is captured, bbox is populated in N/S/E/W inputs."""
        # Create a polygon geometry (triangle)
        points = [
            QgsPointXY(-5.0, 50.0),  # SW
            QgsPointXY(2.0, 50.0),  # SE
            QgsPointXY(-1.5, 55.0),  # N
            QgsPointXY(-5.0, 50.0),  # Close polygon
        ]
        geometry = QgsGeometry.fromPolygonXY([points])

        # Simulate polygon capture
        self.widget.on_polygon_captured(geometry)

        # Verify bbox values are populated (bounding box of the triangle)
        self.assertEqual(self.widget.north_input.value(), 55.0)
        self.assertEqual(self.widget.south_input.value(), 50.0)
        self.assertEqual(self.widget.east_input.value(), 2.0)
        self.assertEqual(self.widget.west_input.value(), -5.0)

    def test_draw_on_canvas_bbox_used_in_search(self):
        """Test end-to-end: draw polygon on canvas, bbox populated, search uses bbox."""
        # Set up mock catalog and collection
        mock_catalog = MagicMock()
        mock_collection = MagicMock()
        mock_collection.id = "test_collection"
        mock_catalog.search.return_value = []

        self.widget.catalog = mock_catalog
        self.widget.collection = mock_collection

        # Simulate user drawing a polygon and the tool emitting the geometry
        # Create an irregular polygon to verify bounding box conversion
        points = [
            QgsPointXY(-3.0, 51.0),
            QgsPointXY(1.0, 52.0),
            QgsPointXY(0.5, 54.0),
            QgsPointXY(-2.0, 53.0),
            QgsPointXY(-3.0, 51.0),  # Close polygon
        ]
        geometry = QgsGeometry.fromPolygonXY([points])

        # This simulates what happens when the polygon tool emits the signal
        self.widget.on_polygon_captured(geometry)

        # Verify bbox was populated from the polygon's bounding box
        bbox = geometry.boundingBox()
        self.assertEqual(self.widget.north_input.value(), bbox.yMaximum())
        self.assertEqual(self.widget.south_input.value(), bbox.yMinimum())
        self.assertEqual(self.widget.east_input.value(), bbox.xMaximum())
        self.assertEqual(self.widget.west_input.value(), bbox.xMinimum())

        # Trigger search
        self.widget.on_search_clicked()

        # Assert search was called with the bbox from the drawn polygon
        mock_catalog.search.assert_called_once()
        call_kwargs = mock_catalog.search.call_args.kwargs

        # Expected bbox: [west, south, east, north]
        expected_bbox = [
            bbox.xMinimum(),
            bbox.yMinimum(),
            bbox.xMaximum(),
            bbox.yMaximum(),
        ]
        self.assertEqual(call_kwargs["bbox"], expected_bbox)

    def test_polygon_captured_transforms_crs_to_wgs84(self):
        """Test that polygon coordinates are transformed from project CRS to WGS84."""
        # Set project CRS to a projected CRS (EPSG:3857 - Web Mercator, uses meters)
        projected_crs = QgsCoordinateReferenceSystem("EPSG:3857")
        QgsProject.instance().setCrs(projected_crs)

        # Create a polygon with coordinates in EPSG:3857 (meters)
        # These coordinates roughly correspond to an area in Western Europe
        # EPSG:3857 coords: x ~ -556597 to 222639 (lon -5 to 2),
        # y ~ 6446275 to 7361866 (lat 50 to 55)
        points = [
            QgsPointXY(-556597.0, 6446275.0),  # SW corner (~lon -5, lat 50)
            QgsPointXY(222639.0, 6446275.0),  # SE corner (~lon 2, lat 50)
            QgsPointXY(222639.0, 7361866.0),  # NE corner (~lon 2, lat 55)
            QgsPointXY(-556597.0, 7361866.0),  # NW corner (~lon -5, lat 55)
            QgsPointXY(-556597.0, 6446275.0),  # Close polygon
        ]
        geometry = QgsGeometry.fromPolygonXY([points])

        # Simulate polygon capture
        self.widget.on_polygon_captured(geometry)

        # Verify that the values are in WGS84 degrees, not meters
        # The values should be roughly: west=-5, south=50, east=2, north=55
        # We use assertAlmostEqual because coordinate transformations
        # may have small floating point differences
        self.assertAlmostEqual(self.widget.west_input.value(), -5.0, delta=0.1)
        self.assertAlmostEqual(self.widget.south_input.value(), 50.0, delta=0.1)
        self.assertAlmostEqual(self.widget.east_input.value(), 2.0, delta=0.1)
        self.assertAlmostEqual(self.widget.north_input.value(), 55.0, delta=0.1)

        # Most importantly: verify that values are NOT in the original meters range
        # If no transformation happened, values would be in the hundreds of thousands
        self.assertLess(abs(self.widget.west_input.value()), 180)
        self.assertLess(abs(self.widget.east_input.value()), 180)
        self.assertLess(abs(self.widget.north_input.value()), 90)
        self.assertLess(abs(self.widget.south_input.value()), 90)

        # Reset project CRS to WGS84 for other tests
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

    def test_use_extent_populates_bbox_from_map_canvas(self):
        """Test that clicking 'Use current extent' populates bbox from map canvas."""
        from qgis.core import QgsRectangle

        # Set project CRS to WGS84
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

        # Create a mock extent (QgsRectangle) representing the visible map area
        mock_extent = QgsRectangle(-5.0, 50.0, 2.0, 55.0)  # xMin, yMin, xMax, yMax
        self.mock_canvas.extent.return_value = mock_extent

        # Trigger use extent button click
        self.widget.on_use_extent_clicked()

        # Verify bbox values are populated from the canvas extent
        self.assertEqual(self.widget.west_input.value(), -5.0)
        self.assertEqual(self.widget.south_input.value(), 50.0)
        self.assertEqual(self.widget.east_input.value(), 2.0)
        self.assertEqual(self.widget.north_input.value(), 55.0)

    def test_use_extent_transforms_crs_to_wgs84(self):
        """Test that map extent is transformed from project CRS to WGS84."""
        from qgis.core import QgsRectangle

        # Set project CRS to EPSG:3857 (Web Mercator, uses meters)
        projected_crs = QgsCoordinateReferenceSystem("EPSG:3857")
        QgsProject.instance().setCrs(projected_crs)

        # Create a mock extent in EPSG:3857 coordinates (meters)
        # These correspond roughly to: west=-5, south=50, east=2, north=55 in WGS84
        mock_extent = QgsRectangle(-556597.0, 6446275.0, 222639.0, 7361866.0)
        self.mock_canvas.extent.return_value = mock_extent

        # Trigger use extent button click
        self.widget.on_use_extent_clicked()

        # Verify values are transformed to WGS84 degrees (not meters)
        self.assertAlmostEqual(self.widget.west_input.value(), -5.0, delta=0.1)
        self.assertAlmostEqual(self.widget.south_input.value(), 50.0, delta=0.1)
        self.assertAlmostEqual(self.widget.east_input.value(), 2.0, delta=0.1)
        self.assertAlmostEqual(self.widget.north_input.value(), 55.0, delta=0.1)

        # Verify values are NOT in meters range
        self.assertLess(abs(self.widget.west_input.value()), 180)
        self.assertLess(abs(self.widget.east_input.value()), 180)
        self.assertLess(abs(self.widget.north_input.value()), 90)
        self.assertLess(abs(self.widget.south_input.value()), 90)

        # Reset project CRS to WGS84 for other tests
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

    def test_date_range_sent_in_search(self):
        """Test that from_date and to_date values are sent in search request."""
        # Set up mock catalog and collection
        mock_catalog = MagicMock()
        mock_collection = MagicMock()
        mock_collection.id = "test_collection"
        mock_catalog.search.return_value = []  # Empty results

        # Use widget without iface for this test
        widget = SearchWidget(iface=None, parent=None)
        widget.catalog = mock_catalog
        widget.collection = mock_collection

        # Set date range values
        widget.from_date.setDate(QtCore.QDate(2024, 6, 15))
        widget.to_date.setDate(QtCore.QDate(2024, 9, 20))

        # Set bbox values (required for search)
        widget.north_input.setValue(55.0)
        widget.south_input.setValue(50.0)
        widget.east_input.setValue(2.0)
        widget.west_input.setValue(-5.0)

        # Trigger search
        widget.on_search_clicked()

        # Assert catalog.search was called with correct date range
        mock_catalog.search.assert_called_once()
        call_kwargs = mock_catalog.search.call_args.kwargs

        # Verify date format is yyyy-MM-dd
        self.assertEqual(call_kwargs["start_datetime"], "2024-06-15")
        self.assertEqual(call_kwargs["end_datetime"], "2024-09-20")

    def test_catalogue_only_search_without_collection(self):
        """Test that search works with only a catalogue (no collection selected)."""
        # Set up mock catalog only - no collection
        mock_catalog = MagicMock()
        mock_catalog.search.return_value = []  # Empty results

        # Use widget without iface for this test
        widget = SearchWidget(iface=None, parent=None)
        widget.catalog = mock_catalog
        widget.collection = None  # No collection selected

        # Set bbox values (required for search)
        widget.north_input.setValue(55.0)
        widget.south_input.setValue(50.0)
        widget.east_input.setValue(2.0)
        widget.west_input.setValue(-5.0)

        # Trigger search
        widget.on_search_clicked()

        # Assert catalog.search was called
        mock_catalog.search.assert_called_once()
        call_kwargs = mock_catalog.search.call_args.kwargs

        # Verify collections parameter is NOT in the call (catalogue-wide search)
        self.assertNotIn("collections", call_kwargs)

        # Verify other parameters are still present
        self.assertEqual(call_kwargs["bbox"], [-5.0, 50.0, 2.0, 55.0])
        self.assertIn("start_datetime", call_kwargs)
        self.assertIn("end_datetime", call_kwargs)

    def test_search_with_collection_includes_collections_param(self):
        """Test that search with a collection includes the collections parameter."""
        # Set up mock catalog and collection
        mock_catalog = MagicMock()
        mock_collection = MagicMock()
        mock_collection.id = "sentinel-2"
        mock_catalog.search.return_value = []

        widget = SearchWidget(iface=None, parent=None)
        widget.catalog = mock_catalog
        widget.collection = mock_collection

        # Set bbox values
        widget.north_input.setValue(55.0)
        widget.south_input.setValue(50.0)
        widget.east_input.setValue(2.0)
        widget.west_input.setValue(-5.0)

        # Trigger search
        widget.on_search_clicked()

        # Assert collections parameter IS in the call
        mock_catalog.search.assert_called_once()
        call_kwargs = mock_catalog.search.call_args.kwargs

        self.assertIn("collections", call_kwargs)
        self.assertEqual(call_kwargs["collections"], ["sentinel-2"])

    def test_pagination_controls_update_after_search(self):
        """Test that pagination controls are updated correctly after a search."""
        # Create mock paginated results with 120 total items
        mock_catalog = MagicMock()
        mock_paginated_list = MagicMock()
        mock_paginated_list.total_count = 120
        # Return 50 items for first page
        mock_paginated_list.__getitem__ = MagicMock(return_value=[MagicMock() for _ in range(50)])
        mock_catalog.search.return_value = mock_paginated_list

        widget = SearchWidget(iface=None, parent=None)
        widget.catalog = mock_catalog

        # Set bbox values
        widget.north_input.setValue(55.0)
        widget.south_input.setValue(50.0)
        widget.east_input.setValue(2.0)
        widget.west_input.setValue(-5.0)

        # Trigger search
        widget.on_search_clicked()

        # Verify pagination state
        self.assertEqual(widget.current_page, 0)
        self.assertEqual(widget.total_results, 120)

        # Verify pagination controls
        # 120 results / 50 per page = 3 pages (ceil)
        self.assertEqual(widget.page_label.text(), "Page 1 of 3")
        self.assertIn("120", widget.results_count_label.text())

        # Previous should be disabled on first page
        self.assertFalse(widget.prev_page_btn.isEnabled())
        # Next should be enabled (more pages available)
        self.assertTrue(widget.next_page_btn.isEnabled())

    def test_pagination_next_page_navigation(self):
        """Test that clicking Next navigates to the next page."""
        # Create mock paginated results
        mock_catalog = MagicMock()
        mock_paginated_list = MagicMock()
        mock_paginated_list.total_count = 120

        # Mock slicing to return different results per page
        def mock_getitem(slice_obj):
            end = slice_obj.stop if isinstance(slice_obj, slice) else slice_obj
            return [MagicMock() for _ in range(min(end, 120))]

        mock_paginated_list.__getitem__ = mock_getitem
        mock_catalog.search.return_value = mock_paginated_list

        widget = SearchWidget(iface=None, parent=None)
        widget.catalog = mock_catalog

        # Set bbox values
        widget.north_input.setValue(55.0)
        widget.south_input.setValue(50.0)
        widget.east_input.setValue(2.0)
        widget.west_input.setValue(-5.0)

        # Trigger search (page 0)
        widget.on_search_clicked()
        self.assertEqual(widget.current_page, 0)
        self.assertEqual(widget.page_label.text(), "Page 1 of 3")

        # Click Next
        widget.on_next_page()

        # Verify we're on page 2
        self.assertEqual(widget.current_page, 1)
        self.assertEqual(widget.page_label.text(), "Page 2 of 3")

        # Now Previous should be enabled
        self.assertTrue(widget.prev_page_btn.isEnabled())
        # Next should still be enabled (page 3 available)
        self.assertTrue(widget.next_page_btn.isEnabled())

    def test_pagination_previous_page_navigation(self):
        """Test that clicking Previous navigates to the previous page."""
        mock_catalog = MagicMock()
        mock_paginated_list = MagicMock()
        mock_paginated_list.total_count = 120

        def mock_getitem(slice_obj):
            end = slice_obj.stop if isinstance(slice_obj, slice) else slice_obj
            return [MagicMock() for _ in range(min(end, 120))]

        mock_paginated_list.__getitem__ = mock_getitem
        mock_catalog.search.return_value = mock_paginated_list

        widget = SearchWidget(iface=None, parent=None)
        widget.catalog = mock_catalog

        # Set bbox values
        widget.north_input.setValue(55.0)
        widget.south_input.setValue(50.0)
        widget.east_input.setValue(2.0)
        widget.west_input.setValue(-5.0)

        # Trigger search and navigate to page 2
        widget.on_search_clicked()
        widget.on_next_page()
        self.assertEqual(widget.current_page, 1)

        # Click Previous
        widget.on_prev_page()

        # Verify we're back on page 1
        self.assertEqual(widget.current_page, 0)
        self.assertEqual(widget.page_label.text(), "Page 1 of 3")

        # Previous should be disabled on first page
        self.assertFalse(widget.prev_page_btn.isEnabled())

    def test_pagination_disabled_on_last_page(self):
        """Test that Next is disabled when on the last page."""
        mock_catalog = MagicMock()
        mock_paginated_list = MagicMock()
        mock_paginated_list.total_count = 75  # 2 pages: 50 + 25

        def mock_getitem(slice_obj):
            end = slice_obj.stop if isinstance(slice_obj, slice) else slice_obj
            return [MagicMock() for _ in range(min(end, 75))]

        mock_paginated_list.__getitem__ = mock_getitem
        mock_catalog.search.return_value = mock_paginated_list

        widget = SearchWidget(iface=None, parent=None)
        widget.catalog = mock_catalog

        # Set bbox values
        widget.north_input.setValue(55.0)
        widget.south_input.setValue(50.0)
        widget.east_input.setValue(2.0)
        widget.west_input.setValue(-5.0)

        # Trigger search
        widget.on_search_clicked()
        self.assertEqual(widget.page_label.text(), "Page 1 of 2")

        # Navigate to last page
        widget.on_next_page()

        # Verify we're on page 2 (last page)
        self.assertEqual(widget.current_page, 1)
        self.assertEqual(widget.page_label.text(), "Page 2 of 2")

        # Next should be disabled on last page
        self.assertFalse(widget.next_page_btn.isEnabled())
        # Previous should be enabled
        self.assertTrue(widget.prev_page_btn.isEnabled())

    @patch.object(QtWidgets.QDialog, "exec")
    def test_asset_selection_dialog_returns_selected_assets(self, mock_exec):
        """Test that asset selection dialog returns only selected assets."""
        # Mock dialog to return Accepted
        mock_exec.return_value = QtWidgets.QDialog.Accepted

        # Create mock assets
        mock_asset1 = MagicMock()
        mock_asset1.type = "image/tiff"
        mock_asset1.extra_fields = {}

        mock_asset2 = MagicMock()
        mock_asset2.type = "application/x-netcdf"
        mock_asset2.extra_fields = {}

        loadable_assets = [("visual", mock_asset1), ("data", mock_asset2)]

        # Call the dialog method
        result = self.widget._show_asset_selection_dialog(loadable_assets, "test-item")

        # Since all checkboxes are checked by default and dialog is accepted,
        # all assets should be returned
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][0], "visual")
        self.assertEqual(result[1][0], "data")

    @patch.object(QtWidgets.QDialog, "exec")
    def test_asset_selection_dialog_returns_empty_on_cancel(self, mock_exec):
        """Test that asset selection dialog returns empty list when cancelled."""
        # Mock dialog to return Rejected (cancelled)
        mock_exec.return_value = QtWidgets.QDialog.Rejected

        mock_asset = MagicMock()
        mock_asset.type = "image/tiff"
        mock_asset.extra_fields = {}

        loadable_assets = [("visual", mock_asset)]

        result = self.widget._show_asset_selection_dialog(loadable_assets, "test-item")

        # Should return empty list when cancelled
        self.assertEqual(result, [])

    def test_single_asset_skips_dialog(self):
        """Test that loading single asset skips selection dialog."""
        # Create a mock item with a single loadable asset
        mock_item = MagicMock()
        mock_item.id = "test-item-single"
        mock_item.assets = {
            "visual": MagicMock(
                href="http://example.com/image.tif",
                type="image/tiff",
                roles=["data"],
            )
        }
        mock_item.properties = {}

        self.widget.search_results = [mock_item]

        # Mock LayerLoaderTask and QgsApplication task manager
        with patch("eodh_qgis.gui.search_widget.LayerLoaderTask") as mock_task_cls:
            mock_task = MagicMock()
            mock_task_cls.return_value = mock_task
            with (
                patch("eodh_qgis.gui.search_widget.QgsApplication"),
                patch.object(self.widget, "_show_asset_selection_dialog") as mock_dialog,
            ):
                # Call _load_item_assets directly
                # (simulates clicking Load Assets button)
                self.widget._load_item_assets(mock_item)

                # Dialog should NOT be called for single asset
                mock_dialog.assert_not_called()

                # A LayerLoaderTask should have been created
                mock_task_cls.assert_called_once()

    def test_footprint_toggle_tracks_selected_items(self):
        """Test that toggling footprint checkbox tracks/untracks items."""
        # Create mock items with geometry
        mock_item1 = MagicMock()
        mock_item1.id = "item-1"
        mock_item1.geometry = {
            "type": "Polygon",
            "coordinates": [[[-5, 50], [2, 50], [2, 55], [-5, 55], [-5, 50]]],
        }

        mock_item2 = MagicMock()
        mock_item2.id = "item-2"
        mock_item2.geometry = {
            "type": "Polygon",
            "coordinates": [[[-3, 51], [1, 51], [1, 54], [-3, 54], [-3, 51]]],
        }

        # Initially no items selected
        self.assertEqual(len(self.widget.selected_footprint_items), 0)
        self.assertEqual(
            self.widget.add_selected_footprints_btn.text(),
            "Add Selected Footprints (0)",
        )
        self.assertFalse(self.widget.add_selected_footprints_btn.isEnabled())

        # Toggle item 1 ON
        self.widget._on_footprint_toggled(mock_item1, True)
        self.assertEqual(len(self.widget.selected_footprint_items), 1)
        self.assertIn("item-1", self.widget.selected_footprint_items)
        self.assertEqual(
            self.widget.add_selected_footprints_btn.text(),
            "Add Selected Footprints (1)",
        )
        self.assertTrue(self.widget.add_selected_footprints_btn.isEnabled())

        # Toggle item 2 ON
        self.widget._on_footprint_toggled(mock_item2, True)
        self.assertEqual(len(self.widget.selected_footprint_items), 2)
        self.assertEqual(
            self.widget.add_selected_footprints_btn.text(),
            "Add Selected Footprints (2)",
        )

        # Toggle item 1 OFF
        self.widget._on_footprint_toggled(mock_item1, False)
        self.assertEqual(len(self.widget.selected_footprint_items), 1)
        self.assertNotIn("item-1", self.widget.selected_footprint_items)
        self.assertIn("item-2", self.widget.selected_footprint_items)
        self.assertEqual(
            self.widget.add_selected_footprints_btn.text(),
            "Add Selected Footprints (1)",
        )

        # Toggle item 2 OFF
        self.widget._on_footprint_toggled(mock_item2, False)
        self.assertEqual(len(self.widget.selected_footprint_items), 0)
        self.assertEqual(
            self.widget.add_selected_footprints_btn.text(),
            "Add Selected Footprints (0)",
        )
        self.assertFalse(self.widget.add_selected_footprints_btn.isEnabled())

    def test_add_footprint_layer_creates_vector_layer(self):
        """Test that _add_footprint_layer creates a valid vector layer."""
        # Create a mock item with valid GeoJSON geometry
        mock_item = MagicMock()
        mock_item.id = "test-footprint-item"
        mock_item.collection = "sentinel-2"
        mock_item.datetime = "2024-01-15T10:30:00Z"
        mock_item.geometry = {
            "type": "Polygon",
            "coordinates": [[[-5.0, 50.0], [2.0, 50.0], [2.0, 55.0], [-5.0, 55.0], [-5.0, 50.0]]],
        }

        # Track layers added to project
        layers_before = list(QgsProject.instance().mapLayers().keys())

        # Add footprint layer
        result = self.widget._add_footprint_layer(mock_item)

        # Verify layer was created successfully
        self.assertTrue(result)

        # Verify a new layer was added to the project
        layers_after = list(QgsProject.instance().mapLayers().keys())
        self.assertEqual(len(layers_after), len(layers_before) + 1)

        # Find the new layer
        new_layer_id = set(layers_after) - set(layers_before)
        self.assertEqual(len(new_layer_id), 1)

        new_layer = QgsProject.instance().mapLayer(new_layer_id.pop())
        self.assertIsNotNone(new_layer)
        self.assertTrue(new_layer.isValid())

        # Verify layer name contains item ID
        self.assertIn("test-footprint-item", new_layer.name())

        # Verify CRS is WGS84
        self.assertEqual(new_layer.crs().authid(), "EPSG:4326")

        # Clean up - remove the test layer
        QgsProject.instance().removeMapLayer(new_layer.id())

    def test_add_footprint_layer_returns_false_without_geometry(self):
        """Test that _add_footprint_layer returns False for items without geometry."""
        # Item with no geometry attribute
        mock_item_no_attr = MagicMock(spec=["id", "collection", "datetime"])
        mock_item_no_attr.id = "no-geometry-item"
        result = self.widget._add_footprint_layer(mock_item_no_attr)
        self.assertFalse(result)

        # Item with None geometry
        mock_item_none = MagicMock()
        mock_item_none.id = "none-geometry-item"
        mock_item_none.geometry = None
        result = self.widget._add_footprint_layer(mock_item_none)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
