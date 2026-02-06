"""Tests for geometry utility functions."""

import unittest
from unittest.mock import Mock

from eodh_qgis.geometry_utils import (
    _create_polar_cap_geometry,
    _get_geometry_lon_span,
    add_footprint_to_project,
    create_footprint_layer,
    item_has_geometry,
)


class TestItemHasGeometry(unittest.TestCase):
    """Tests for item_has_geometry function."""

    def test_returns_true_with_valid_geometry(self):
        """Test returns True when item has valid geometry."""
        item = Mock()
        item.geometry = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
        }
        self.assertTrue(item_has_geometry(item))

    def test_returns_false_with_none_geometry(self):
        """Test returns False when geometry is None."""
        item = Mock()
        item.geometry = None
        self.assertFalse(item_has_geometry(item))

    def test_returns_false_without_geometry_attribute(self):
        """Test returns False when item has no geometry attribute."""
        item = Mock(spec=[])  # Mock without geometry attribute
        self.assertFalse(item_has_geometry(item))


class TestCreateFootprintLayer(unittest.TestCase):
    """Tests for create_footprint_layer function."""

    def test_returns_none_without_geometry(self):
        """Test returns None when item has no geometry."""
        item = Mock()
        item.geometry = None
        result = create_footprint_layer(item)
        self.assertIsNone(result)

    def test_returns_none_without_geometry_attribute(self):
        """Test returns None when item has no geometry attribute."""
        item = Mock(spec=[])
        result = create_footprint_layer(item)
        self.assertIsNone(result)

    def test_creates_valid_layer_with_polygon(self):
        """Test creates a valid layer from polygon geometry."""
        item = Mock()
        item.id = "test-item-123"
        item.geometry = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
        }
        item.collection = "test-collection"
        item.datetime = "2024-01-15T10:30:00Z"

        layer = create_footprint_layer(item)

        self.assertIsNotNone(layer)
        self.assertTrue(layer.isValid())
        self.assertEqual(layer.name(), "test-item-123_footprint")
        self.assertEqual(layer.crs().authid(), "EPSG:4326")

    def test_uses_custom_layer_name(self):
        """Test uses custom layer name when provided."""
        item = Mock()
        item.id = "test-item"
        item.geometry = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
        }
        item.collection = None
        item.datetime = None

        layer = create_footprint_layer(item, layer_name="custom_name")

        self.assertIsNotNone(layer)
        self.assertEqual(layer.name(), "custom_name")

    def test_handles_multipolygon_geometry(self):
        """Test handles MultiPolygon geometry type."""
        item = Mock()
        item.id = "multi-polygon-item"
        item.geometry = {
            "type": "MultiPolygon",
            "coordinates": [
                [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                [[[2, 2], [3, 2], [3, 3], [2, 3], [2, 2]]],
            ],
        }
        item.collection = None
        item.datetime = None

        layer = create_footprint_layer(item)

        self.assertIsNotNone(layer)
        self.assertTrue(layer.isValid())


class TestAddFootprintToProject(unittest.TestCase):
    """Tests for add_footprint_to_project function."""

    def test_returns_false_without_geometry(self):
        """Test returns False when item has no geometry."""
        item = Mock()
        item.geometry = None

        result = add_footprint_to_project(item)

        self.assertFalse(result)

    def test_returns_true_with_valid_geometry(self):
        """Test returns True when layer is added successfully."""
        item = Mock()
        item.id = "test-item"
        item.geometry = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
        }
        item.collection = None
        item.datetime = None

        result = add_footprint_to_project(item)

        self.assertTrue(result)


class TestGetGeometryLonSpan(unittest.TestCase):
    """Tests for _get_geometry_lon_span function."""

    def test_polygon_lon_span(self):
        """Test calculating lon span for a polygon."""
        geometry = {
            "type": "Polygon",
            "coordinates": [[[-10, 40], [20, 40], [20, 60], [-10, 60], [-10, 40]]],
        }
        result = _get_geometry_lon_span(geometry)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result[0], 30.0)  # lon span
        self.assertAlmostEqual(result[1], 40.0)  # min lat
        self.assertAlmostEqual(result[2], 60.0)  # max lat

    def test_none_geometry(self):
        """Test None geometry returns None."""
        self.assertIsNone(_get_geometry_lon_span(None))

    def test_empty_coordinates(self):
        """Test empty coordinates returns None."""
        self.assertIsNone(_get_geometry_lon_span({"type": "Polygon", "coordinates": []}))

    def test_no_coordinates_key(self):
        """Test missing coordinates key returns None."""
        self.assertIsNone(_get_geometry_lon_span({"type": "Polygon"}))

    def test_multipolygon(self):
        """Test lon span for MultiPolygon."""
        geometry = {
            "type": "MultiPolygon",
            "coordinates": [
                [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
                [[[20, 20], [30, 20], [30, 30], [20, 30], [20, 20]]],
            ],
        }
        result = _get_geometry_lon_span(geometry)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result[0], 30.0)


class TestCreatePolarCapGeometry(unittest.TestCase):
    """Tests for _create_polar_cap_geometry function."""

    def test_creates_polygon(self):
        """Test that a polygon geometry is created."""
        geom = _create_polar_cap_geometry(60.0, 90.0)
        self.assertEqual(geom["type"], "Polygon")
        self.assertEqual(len(geom["coordinates"]), 1)
        self.assertEqual(len(geom["coordinates"][0]), 5)

    def test_lat_bounds(self):
        """Test that latitude bounds are correct."""
        geom = _create_polar_cap_geometry(60.0, 90.0)
        coords = geom["coordinates"][0]
        lats = [c[1] for c in coords]
        self.assertEqual(min(lats), 60.0)
        self.assertEqual(max(lats), 90.0)

    def test_full_longitude_range(self):
        """Test that longitude spans -180 to 180."""
        geom = _create_polar_cap_geometry(60.0, 90.0)
        coords = geom["coordinates"][0]
        lons = [c[0] for c in coords]
        self.assertIn(-180, lons)
        self.assertIn(180, lons)


class TestCreateFootprintLayerPolar(unittest.TestCase):
    """Tests for create_footprint_layer with polar geometries."""

    def test_polar_spanning_geometry_uses_cap(self):
        """Test that wide-spanning geometry gets simplified to polar cap."""
        item = Mock()
        item.id = "polar-item"
        item.collection = None
        item.datetime = None
        # Geometry spanning nearly full longitude range
        item.geometry = {
            "type": "Polygon",
            "coordinates": [[[-179, 60], [179, 60], [179, 90], [-179, 90], [-179, 60]]],
        }

        layer = create_footprint_layer(item)
        self.assertIsNotNone(layer)
        self.assertTrue(layer.isValid())


if __name__ == "__main__":
    unittest.main()
