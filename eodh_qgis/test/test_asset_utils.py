"""Tests for asset utility functions."""

import unittest
from unittest.mock import Mock

from eodh_qgis.asset_utils import (
    extract_epsg_from_asset,
    format_assets_with_crs,
    format_bbox,
    get_all_loadable_assets,
    get_asset_file_type,
    is_loadable_asset,
)


class TestFormatBbox(unittest.TestCase):
    """Tests for format_bbox function."""

    def test_valid_bbox(self):
        """Test formatting a valid bbox."""
        bbox = [-180.0, -90.0, 180.0, 90.0]
        result = format_bbox(bbox)
        self.assertEqual(result, "W: -180.00, S: -90.00, E: 180.00, N: 90.00")

    def test_bbox_with_decimals(self):
        """Test formatting bbox with decimal values."""
        bbox = [-10.5, 45.25, 20.75, 60.125]
        result = format_bbox(bbox)
        self.assertEqual(result, "W: -10.50, S: 45.25, E: 20.75, N: 60.12")

    def test_none_bbox(self):
        """Test None bbox returns N/A."""
        result = format_bbox(None)
        self.assertEqual(result, "N/A")

    def test_empty_bbox(self):
        """Test empty bbox returns N/A."""
        result = format_bbox([])
        self.assertEqual(result, "N/A")

    def test_invalid_bbox_length(self):
        """Test bbox with wrong number of elements returns N/A."""
        result = format_bbox([1, 2, 3])
        self.assertEqual(result, "N/A")


class TestGetAssetFileType(unittest.TestCase):
    """Tests for get_asset_file_type function."""

    def test_geotiff_mime_type(self):
        """Test GeoTIFF detection from MIME type."""
        asset = Mock()
        asset.type = "image/tiff; application=geotiff"
        asset.href = "file.tif"
        self.assertEqual(get_asset_file_type(asset), "GeoTIFF")

    def test_cog_mime_type(self):
        """Test COG detection from MIME type."""
        asset = Mock()
        asset.type = "image/tiff; application=geotiff; profile=cloud-optimized"
        asset.href = "file.tif"
        self.assertEqual(get_asset_file_type(asset), "COG")

    def test_netcdf_mime_type(self):
        """Test NetCDF detection from MIME type."""
        asset = Mock()
        asset.type = "application/x-netcdf"
        asset.href = "file.nc"
        self.assertEqual(get_asset_file_type(asset), "NetCDF")

    def test_png_mime_type(self):
        """Test PNG detection from MIME type."""
        asset = Mock()
        asset.type = "image/png"
        asset.href = "file.png"
        self.assertEqual(get_asset_file_type(asset), "PNG")

    def test_tiff_extension_fallback(self):
        """Test GeoTIFF detection from file extension."""
        asset = Mock()
        asset.type = None
        asset.href = "https://example.com/file.tiff"
        self.assertEqual(get_asset_file_type(asset), "GeoTIFF")

    def test_nc_extension_fallback(self):
        """Test NetCDF detection from file extension."""
        asset = Mock()
        asset.type = None
        asset.href = "https://example.com/file.nc"
        self.assertEqual(get_asset_file_type(asset), "NetCDF")

    def test_unknown_type(self):
        """Test unknown type returns Unknown."""
        asset = Mock()
        asset.type = None
        asset.href = ""
        self.assertEqual(get_asset_file_type(asset), "Unknown")

    def test_raw_extension(self):
        """Test raw extension is returned for unknown types."""
        asset = Mock()
        asset.type = None
        asset.href = "https://example.com/file.zarr"
        self.assertEqual(get_asset_file_type(asset), ".ZARR")


class TestIsLoadableAsset(unittest.TestCase):
    """Tests for is_loadable_asset function."""

    def test_cog_is_loadable(self):
        """Test COG asset is loadable."""
        asset = Mock()
        asset.type = "image/tiff; application=geotiff; profile=cloud-optimized"
        asset.href = "https://example.com/file.tif"
        asset.roles = ["data"]
        self.assertTrue(is_loadable_asset(asset))

    def test_netcdf_is_loadable(self):
        """Test NetCDF asset is loadable."""
        asset = Mock()
        asset.type = "application/x-netcdf"
        asset.href = "https://example.com/file.nc"
        asset.roles = ["data"]
        self.assertTrue(is_loadable_asset(asset))

    def test_thumbnail_is_not_loadable(self):
        """Test thumbnail assets are not loadable."""
        asset = Mock()
        asset.type = "image/png"
        asset.href = "https://example.com/thumb.png"
        asset.roles = ["thumbnail"]
        self.assertFalse(is_loadable_asset(asset, "thumbnail"))

    def test_no_href_is_not_loadable(self):
        """Test asset without href is not loadable."""
        asset = Mock(spec=[])
        self.assertFalse(is_loadable_asset(asset))

    def test_tiff_extension_is_loadable(self):
        """Test tiff extension makes asset loadable."""
        asset = Mock()
        asset.type = None
        asset.href = "https://example.com/file.tif"
        asset.roles = []
        self.assertTrue(is_loadable_asset(asset))


class TestGetAllLoadableAssets(unittest.TestCase):
    """Tests for get_all_loadable_assets function."""

    def test_returns_loadable_assets(self):
        """Test that loadable assets are returned."""
        data_asset = Mock()
        data_asset.type = "image/tiff; application=geotiff"
        data_asset.href = "https://example.com/data.tif"
        data_asset.roles = ["data"]

        thumb_asset = Mock()
        thumb_asset.type = "image/png"
        thumb_asset.href = "https://example.com/thumb.png"
        thumb_asset.roles = ["thumbnail"]

        item = Mock()
        item.assets = {"data": data_asset, "thumbnail": thumb_asset}

        loadable = get_all_loadable_assets(item)
        self.assertEqual(len(loadable), 1)
        self.assertEqual(loadable[0][0], "data")

    def test_empty_assets(self):
        """Test empty assets returns empty list."""
        item = Mock()
        item.assets = {}

        loadable = get_all_loadable_assets(item)
        self.assertEqual(loadable, [])


class TestExtractEpsgFromAsset(unittest.TestCase):
    """Tests for extract_epsg_from_asset function."""

    def test_extract_from_proj_epsg(self):
        """Test extracting EPSG from proj:epsg field."""
        asset = Mock()
        asset.extra_fields = {"proj:epsg": 4326}
        # Mock the ext.proj to not be present
        del asset.ext
        self.assertEqual(extract_epsg_from_asset(asset), "4326")

    def test_extract_from_proj_code(self):
        """Test extracting EPSG from proj:code field."""
        asset = Mock()
        asset.extra_fields = {"proj:code": "EPSG:32632"}
        del asset.ext
        self.assertEqual(extract_epsg_from_asset(asset), "32632")

    def test_no_epsg_returns_none(self):
        """Test that None is returned when no EPSG found."""
        asset = Mock()
        asset.extra_fields = {}
        del asset.ext
        self.assertIsNone(extract_epsg_from_asset(asset))


class TestFormatAssetsWithCrs(unittest.TestCase):
    """Tests for format_assets_with_crs function."""

    def test_format_with_crs(self):
        """Test formatting assets with CRS info."""
        asset = Mock()
        asset.type = "image/tiff; application=geotiff"
        asset.href = "file.tif"
        asset.extra_fields = {"proj:epsg": 4326}
        del asset.ext

        item = Mock()
        item.assets = {"data": asset}

        result = format_assets_with_crs(item)
        self.assertIn("data", result)
        self.assertIn("GeoTIFF", result)
        self.assertIn("4326", result)

    def test_no_assets_returns_na(self):
        """Test that N/A is returned for item with no assets."""
        item = Mock()
        item.assets = {}
        self.assertEqual(format_assets_with_crs(item), "N/A")


if __name__ == "__main__":
    unittest.main()
