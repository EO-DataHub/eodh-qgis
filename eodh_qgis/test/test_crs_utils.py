"""Tests for CRS extraction utilities."""

import unittest
from unittest.mock import Mock

from qgis.core import QgsCoordinateReferenceSystem, QgsRasterLayer

from eodh_qgis.crs_utils import apply_crs_to_layer, extract_epsg_from_item


class TestExtractEpsgFromItem(unittest.TestCase):
    """Tests for extract_epsg_from_item function."""

    def test_proj_epsg_integer(self):
        """Test extracting EPSG from proj:epsg as integer."""
        item = Mock()
        item.properties = {"proj:epsg": 4326}
        self.assertEqual(extract_epsg_from_item(item), "4326")

    def test_proj_code_string(self):
        """Test extracting EPSG from proj:code as EPSG:XXXX string."""
        item = Mock()
        item.properties = {"proj:code": "EPSG:32632"}
        self.assertEqual(extract_epsg_from_item(item), "32632")

    def test_epsg_key(self):
        """Test extracting from 'epsg' key."""
        item = Mock()
        item.properties = {"epsg": 3413}
        self.assertEqual(extract_epsg_from_item(item), "3413")

    def test_crs_key(self):
        """Test extracting from 'crs' key."""
        item = Mock()
        item.properties = {"crs": "EPSG:4326"}
        self.assertEqual(extract_epsg_from_item(item), "4326")

    def test_no_epsg_returns_na(self):
        """Test that missing EPSG returns N/A."""
        item = Mock()
        item.properties = {"cloud_cover": 5}
        self.assertEqual(extract_epsg_from_item(item), "N/A")

    def test_empty_properties(self):
        """Test with empty properties."""
        item = Mock()
        item.properties = {}
        self.assertEqual(extract_epsg_from_item(item), "N/A")

    def test_priority_order(self):
        """Test that proj:epsg takes priority over other keys."""
        item = Mock()
        item.properties = {"proj:epsg": 4326, "crs": "EPSG:3857"}
        self.assertEqual(extract_epsg_from_item(item), "4326")

    def test_falsy_value_skipped(self):
        """Test that falsy values (0, None, '') are skipped."""
        item = Mock()
        item.properties = {"proj:epsg": 0, "epsg": 4326}
        self.assertEqual(extract_epsg_from_item(item), "4326")


class TestApplyCrsToLayer(unittest.TestCase):
    """Tests for apply_crs_to_layer function."""

    def test_layer_with_existing_valid_crs(self):
        """Test that layer with existing CRS is left unchanged."""
        layer = Mock(spec=QgsRasterLayer)
        layer.name.return_value = "test_layer"
        crs = QgsCoordinateReferenceSystem("EPSG:4326")
        layer.crs.return_value = crs

        asset = Mock()
        asset.extra_fields = {}
        del asset.ext

        result = apply_crs_to_layer(layer, asset, None, None)
        self.assertTrue(result)
        layer.setCrs.assert_not_called()

    def test_apply_asset_epsg(self):
        """Test applying CRS from asset-level EPSG."""
        layer = Mock(spec=QgsRasterLayer)
        layer.name.return_value = "test_layer"
        invalid_crs = QgsCoordinateReferenceSystem()
        layer.crs.return_value = invalid_crs

        asset = Mock()
        asset.extra_fields = {"proj:epsg": 32632}
        del asset.ext

        result = apply_crs_to_layer(layer, asset, None, None)
        self.assertTrue(result)
        layer.setCrs.assert_called_once()

    def test_apply_item_epsg(self):
        """Test applying CRS from item-level EPSG."""
        layer = Mock(spec=QgsRasterLayer)
        layer.name.return_value = "test_layer"
        invalid_crs = QgsCoordinateReferenceSystem()
        layer.crs.return_value = invalid_crs

        asset = Mock()
        asset.extra_fields = {}
        del asset.ext

        result = apply_crs_to_layer(layer, asset, "4326", None)
        self.assertTrue(result)
        layer.setCrs.assert_called_once()

    def test_apply_metadata_epsg(self):
        """Test applying CRS from metadata XML EPSG."""
        layer = Mock(spec=QgsRasterLayer)
        layer.name.return_value = "test_layer"
        invalid_crs = QgsCoordinateReferenceSystem()
        layer.crs.return_value = invalid_crs

        asset = Mock()
        asset.extra_fields = {}
        del asset.ext

        result = apply_crs_to_layer(layer, asset, "N/A", "3413")
        self.assertTrue(result)
        layer.setCrs.assert_called_once()

    def test_no_crs_found(self):
        """Test returns False when no CRS source is available."""
        layer = Mock(spec=QgsRasterLayer)
        layer.name.return_value = "test_layer"
        layer.source.return_value = "/path/to/file.tif"
        invalid_crs = QgsCoordinateReferenceSystem()
        layer.crs.return_value = invalid_crs

        asset = Mock()
        asset.extra_fields = {}
        del asset.ext

        result = apply_crs_to_layer(layer, asset, "N/A", None)
        self.assertFalse(result)

    def test_item_epsg_na_skipped(self):
        """Test that item_epsg='N/A' is skipped."""
        layer = Mock(spec=QgsRasterLayer)
        layer.name.return_value = "test_layer"
        layer.source.return_value = "/path/to/file.tif"
        invalid_crs = QgsCoordinateReferenceSystem()
        layer.crs.return_value = invalid_crs

        asset = Mock()
        asset.extra_fields = {}
        del asset.ext

        result = apply_crs_to_layer(layer, asset, "N/A", None)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
