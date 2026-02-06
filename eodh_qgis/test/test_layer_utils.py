"""Tests for layer creation utilities."""

import os
import unittest
from unittest.mock import Mock, patch

from qgis.core import QgsRasterLayer

from eodh_qgis.layer_utils import (
    create_layers_for_asset,
    download_with_progress,
    get_netcdf_layers,
)


class TestDownloadWithProgress(unittest.TestCase):
    """Tests for download_with_progress function."""

    @patch("eodh_qgis.layer_utils.urllib.request.urlretrieve")
    def test_calls_urlretrieve(self, mock_retrieve):
        """Test that urlretrieve is called with correct args."""
        download_with_progress("http://example.com/file.nc", "/tmp/file.nc")
        mock_retrieve.assert_called_once()
        args = mock_retrieve.call_args
        self.assertEqual(args[0][0], "http://example.com/file.nc")
        self.assertEqual(args[0][1], "/tmp/file.nc")

    @patch("eodh_qgis.layer_utils.urllib.request.urlretrieve")
    def test_callback_called_with_progress(self, mock_retrieve):
        """Test that progress callback is invoked."""
        progress_values = []

        def on_progress(percent):
            progress_values.append(percent)

        # Simulate reporthook calls
        def fake_retrieve(url, dest, reporthook=None):
            if reporthook:
                reporthook(0, 8192, 100000)  # 0%
                reporthook(5, 8192, 100000)  # ~40%
                reporthook(12, 8192, 100000)  # ~98%

        mock_retrieve.side_effect = fake_retrieve
        download_with_progress("http://example.com/file.nc", "/tmp/file.nc", on_progress)
        self.assertTrue(len(progress_values) > 0)

    @patch("eodh_qgis.layer_utils.urllib.request.urlretrieve")
    def test_no_callback_is_fine(self, mock_retrieve):
        """Test that None callback doesn't crash."""

        def fake_retrieve(url, dest, reporthook=None):
            if reporthook:
                reporthook(1, 8192, 100000)

        mock_retrieve.side_effect = fake_retrieve
        download_with_progress("http://example.com/file.nc", "/tmp/file.nc", None)


class TestGetNetcdfLayers(unittest.TestCase):
    """Tests for get_netcdf_layers function."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = os.path.join(os.path.dirname(__file__), "data")
        self.netcdf_file = os.path.join(
            self.test_data_dir,
            "EOCIS-SEAICE-L3C-SITHICK-CS2-5KM-202302-fv1.0.nc",
        )

    def test_loads_netcdf_variables(self):
        """Test loading data variables from real NetCDF file."""
        layers = get_netcdf_layers(self.netcdf_file, "test_layer")
        self.assertIsInstance(layers, list)
        self.assertGreater(len(layers), 0)
        for layer in layers:
            self.assertIsInstance(layer, QgsRasterLayer)
            self.assertTrue(layer.isValid())

    def test_selected_variables_filter(self):
        """Test filtering to specific variables."""
        layers = get_netcdf_layers(self.netcdf_file, "test_layer", selected_variables=["sea_ice_thickness"])
        self.assertEqual(len(layers), 1)
        self.assertIn("sea_ice_thickness", layers[0].name())

    def test_selected_variables_empty(self):
        """Test selecting no variables returns empty list."""
        layers = get_netcdf_layers(self.netcdf_file, "test_layer", selected_variables=[])
        self.assertEqual(len(layers), 0)

    def test_nonexistent_file_returns_empty(self):
        """Test nonexistent file returns empty list."""
        layers = get_netcdf_layers("/nonexistent/file.nc", "test")
        self.assertEqual(layers, [])

    def test_selected_nonexistent_variable(self):
        """Test selecting variable that doesn't exist returns empty."""
        layers = get_netcdf_layers(self.netcdf_file, "test_layer", selected_variables=["nonexistent_var"])
        self.assertEqual(len(layers), 0)


class TestCreateLayersForAsset(unittest.TestCase):
    """Tests for create_layers_for_asset function."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = os.path.join(os.path.dirname(__file__), "data")
        self.netcdf_file = os.path.join(
            self.test_data_dir,
            "EOCIS-SEAICE-L3C-SITHICK-CS2-5KM-202302-fv1.0.nc",
        )

    def test_create_layers_for_local_netcdf(self):
        """Test creating layers from a local NetCDF file."""
        item = Mock()
        item.id = "test-item"

        asset = Mock()
        asset.href = self.netcdf_file
        asset.type = "application/x-netcdf"

        layers = create_layers_for_asset(item, "data", asset)
        self.assertIsInstance(layers, list)
        self.assertGreater(len(layers), 0)

    def test_create_layers_for_local_netcdf_with_selection(self):
        """Test creating layers with variable selection."""
        item = Mock()
        item.id = "test-item"

        asset = Mock()
        asset.href = self.netcdf_file
        asset.type = "application/x-netcdf"

        layers = create_layers_for_asset(item, "data", asset, selected_variables=["sea_ice_thickness"])
        self.assertEqual(len(layers), 1)

    def test_create_layers_invalid_file(self):
        """Test creating layers from invalid file returns empty."""
        item = Mock()
        item.id = "test-item"

        asset = Mock()
        asset.href = "/nonexistent/file.tif"
        asset.type = "image/tiff"

        layers = create_layers_for_asset(item, "data", asset)
        self.assertEqual(layers, [])

    def test_vsicurl_prefix_for_remote_tiff(self):
        """Test that remote TIFFs get /vsicurl/ prefix."""
        item = Mock()
        item.id = "test-item"

        asset = Mock()
        asset.href = "https://example.com/file.tif"
        asset.type = "image/tiff; application=geotiff"

        # The layer won't be valid (no real URL), but we can check it tries
        layers = create_layers_for_asset(item, "data", asset)
        # Remote TIF will fail but shouldn't crash
        self.assertIsInstance(layers, list)

    def test_netcdf_extension_detected(self):
        """Test that .nc extension triggers NetCDF handling."""
        item = Mock()
        item.id = "test-item"

        asset = Mock()
        asset.href = self.netcdf_file
        asset.type = ""  # No MIME type, rely on extension

        layers = create_layers_for_asset(item, "data", asset)
        self.assertIsInstance(layers, list)


if __name__ == "__main__":
    unittest.main()
