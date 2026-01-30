"""Tests for API data models."""

import unittest
from datetime import datetime
from unittest.mock import Mock

from eodh_qgis.api.models import (
    AssetInfo,
    ConnectionSettings,
    ItemResult,
    SearchFilters,
)


class TestConnectionSettings(unittest.TestCase):
    """Tests for ConnectionSettings dataclass."""

    def test_basic_creation(self):
        """Test creating a basic connection settings."""
        conn = ConnectionSettings(
            name="Test Connection",
            url="https://api.example.com/stac",
        )
        self.assertEqual(conn.name, "Test Connection")
        self.assertEqual(conn.url, "https://api.example.com/stac")
        self.assertIsNone(conn.auth_config_id)
        self.assertEqual(conn.environment, "production")

    def test_with_auth_config(self):
        """Test creating connection with auth config."""
        conn = ConnectionSettings(
            name="Secure Connection",
            url="https://api.example.com/stac",
            auth_config_id="abc123",
            environment="staging",
        )
        self.assertEqual(conn.auth_config_id, "abc123")
        self.assertEqual(conn.environment, "staging")


class TestSearchFilters(unittest.TestCase):
    """Tests for SearchFilters dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        filters = SearchFilters()
        self.assertIsNone(filters.bbox)
        self.assertIsNone(filters.start_date)
        self.assertIsNone(filters.end_date)
        self.assertEqual(filters.collections, [])
        self.assertEqual(filters.limit, 50)

    def test_with_all_params(self):
        """Test creating with all parameters."""
        filters = SearchFilters(
            bbox=(-10.0, 45.0, 20.0, 60.0),
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            collections=["collection-1", "collection-2"],
            limit=100,
        )
        self.assertEqual(filters.bbox, (-10.0, 45.0, 20.0, 60.0))
        self.assertEqual(filters.limit, 100)
        self.assertEqual(len(filters.collections), 2)

    def test_to_search_params_minimal(self):
        """Test conversion to search params with minimal data."""
        filters = SearchFilters()
        params = filters.to_search_params()
        self.assertEqual(params, {"limit": 50})

    def test_to_search_params_with_bbox(self):
        """Test conversion includes bbox when set."""
        filters = SearchFilters(bbox=(-10.0, 45.0, 20.0, 60.0))
        params = filters.to_search_params()
        self.assertIn("bbox", params)
        self.assertEqual(params["bbox"], [-10.0, 45.0, 20.0, 60.0])

    def test_to_search_params_with_datetime(self):
        """Test conversion includes datetime range."""
        filters = SearchFilters(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
        )
        params = filters.to_search_params()
        self.assertIn("datetime", params)
        self.assertIn("2024-01-01", params["datetime"])

    def test_to_search_params_with_collections(self):
        """Test conversion includes collections."""
        filters = SearchFilters(collections=["collection-1"])
        params = filters.to_search_params()
        self.assertIn("collections", params)
        self.assertEqual(params["collections"], ["collection-1"])

    def test_to_search_params_start_date_only(self):
        """Test conversion with only start date (open-ended range)."""
        filters = SearchFilters(start_date=datetime(2024, 6, 1))
        params = filters.to_search_params()
        self.assertIn("datetime", params)
        self.assertTrue(params["datetime"].endswith("/.."))
        self.assertIn("2024-06-01", params["datetime"])

    def test_to_search_params_end_date_only(self):
        """Test conversion with only end date (open-ended range)."""
        filters = SearchFilters(end_date=datetime(2024, 12, 31))
        params = filters.to_search_params()
        self.assertIn("datetime", params)
        self.assertTrue(params["datetime"].startswith("../"))
        self.assertIn("2024-12-31", params["datetime"])


class TestAssetInfo(unittest.TestCase):
    """Tests for AssetInfo dataclass."""

    def test_basic_creation(self):
        """Test creating basic asset info."""
        asset = AssetInfo(
            key="data",
            href="https://example.com/data.tif",
            file_type="GeoTIFF",
        )
        self.assertEqual(asset.key, "data")
        self.assertEqual(asset.href, "https://example.com/data.tif")
        self.assertEqual(asset.file_type, "GeoTIFF")
        self.assertIsNone(asset.epsg)
        self.assertEqual(asset.roles, [])

    def test_from_stac_asset(self):
        """Test creating from a mock STAC asset."""
        mock_asset = Mock()
        mock_asset.href = "https://example.com/data.tif"
        mock_asset.type = "image/tiff; application=geotiff"
        mock_asset.roles = ["data"]
        mock_asset.extra_fields = {"proj:epsg": 4326}
        del mock_asset.ext  # Ensure ext attribute doesn't exist

        asset = AssetInfo.from_stac_asset("data", mock_asset)

        self.assertEqual(asset.key, "data")
        self.assertEqual(asset.href, "https://example.com/data.tif")
        self.assertEqual(asset.file_type, "GeoTIFF")
        self.assertEqual(asset.epsg, "4326")
        self.assertEqual(asset.roles, ["data"])


class TestItemResult(unittest.TestCase):
    """Tests for ItemResult dataclass."""

    def test_basic_creation(self):
        """Test creating basic item result."""
        item = ItemResult(id="test-item-1")
        self.assertEqual(item.id, "test-item-1")
        self.assertIsNone(item.collection)
        self.assertIsNone(item.datetime)
        self.assertIsNone(item.bbox)
        self.assertIsNone(item.geometry)
        self.assertEqual(item.assets, {})
        self.assertEqual(item.properties, {})

    def test_has_geometry_true(self):
        """Test has_geometry returns True when geometry exists."""
        item = ItemResult(
            id="test-item",
            geometry={"type": "Polygon", "coordinates": []},
        )
        self.assertTrue(item.has_geometry())

    def test_has_geometry_false(self):
        """Test has_geometry returns False when no geometry."""
        item = ItemResult(id="test-item")
        self.assertFalse(item.has_geometry())

    def test_from_stac_item(self):
        """Test creating from a mock STAC item."""
        mock_item = Mock()
        mock_item.id = "test-item-123"
        mock_item.collection = "test-collection"
        mock_item.datetime = datetime(2024, 1, 15, 10, 30, 0)
        mock_item.bbox = [-10.5, 45.25, 20.75, 60.125]
        mock_item.geometry = {
            "type": "Polygon",
            "coordinates": [[[-10.5, 45.25], [20.75, 60.125], [-10.5, 45.25]]],
        }
        mock_item.properties = {"cloud_cover": 5}

        # Create mock assets
        mock_asset = Mock()
        mock_asset.href = "https://example.com/data.tif"
        mock_asset.type = "image/tiff"
        mock_asset.roles = ["data"]
        mock_asset.extra_fields = {}
        del mock_asset.ext
        mock_item.assets = {"data": mock_asset}

        item = ItemResult.from_stac_item(mock_item)

        self.assertEqual(item.id, "test-item-123")
        self.assertEqual(item.collection, "test-collection")
        self.assertEqual(item.datetime, datetime(2024, 1, 15, 10, 30, 0))
        self.assertEqual(item.bbox, (-10.5, 45.25, 20.75, 60.125))
        self.assertTrue(item.has_geometry())
        self.assertIn("data", item.assets)
        self.assertEqual(item.properties.get("cloud_cover"), 5)

    def test_from_stac_item_string_datetime(self):
        """Test creating from STAC item with string datetime."""
        mock_item = Mock()
        mock_item.id = "string-dt-item"
        mock_item.collection = None
        mock_item.datetime = "2024-06-15T12:00:00Z"
        mock_item.bbox = None
        mock_item.geometry = None
        mock_item.properties = {}
        mock_item.assets = {}

        item = ItemResult.from_stac_item(mock_item)
        self.assertEqual(item.id, "string-dt-item")
        self.assertIsNotNone(item.datetime)
        self.assertEqual(item.datetime.year, 2024)
        self.assertEqual(item.datetime.month, 6)

    def test_from_stac_item_invalid_string_datetime(self):
        """Test creating from STAC item with invalid string datetime."""
        mock_item = Mock()
        mock_item.id = "bad-dt-item"
        mock_item.collection = None
        mock_item.datetime = "not-a-date"
        mock_item.bbox = None
        mock_item.geometry = None
        mock_item.properties = {}
        mock_item.assets = {}

        item = ItemResult.from_stac_item(mock_item)
        self.assertIsNone(item.datetime)

    def test_from_stac_item_no_assets(self):
        """Test creating from STAC item with no assets."""
        mock_item = Mock()
        mock_item.id = "no-assets"
        mock_item.collection = None
        mock_item.datetime = None
        mock_item.bbox = None
        mock_item.geometry = None
        mock_item.properties = {}
        mock_item.assets = None

        item = ItemResult.from_stac_item(mock_item)
        self.assertEqual(item.assets, {})


class TestMockStacServer(unittest.TestCase):
    """Tests for MockStacServer."""

    def test_server_starts_and_stops(self):
        """Test server can start and stop cleanly."""
        from eodh_qgis.test.mock import MockStacServer

        with MockStacServer() as server:
            self.assertTrue(server.url.startswith("http://localhost:"))
            self.assertIsNotNone(server.server)

    def test_server_responds_to_requests(self):
        """Test server responds to HTTP requests."""
        import urllib.request

        from eodh_qgis.test.mock import MockStacServer

        with MockStacServer() as server:
            # Make a request to the catalogs endpoint
            req = urllib.request.Request(f"{server.url}/catalogs")
            with urllib.request.urlopen(req) as response:
                data = response.read()
                self.assertIn(b"test-catalog", data)


if __name__ == "__main__":
    unittest.main()
