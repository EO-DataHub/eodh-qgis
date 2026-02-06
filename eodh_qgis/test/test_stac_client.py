"""Tests for STAC API client."""

import unittest
from unittest.mock import Mock

from eodh_qgis.api.client import StacClient
from eodh_qgis.api.models import ConnectionSettings, SearchFilters


class TestStacClientInit(unittest.TestCase):
    """Tests for StacClient initialization."""

    def test_init(self):
        """Test basic initialization."""
        conn = ConnectionSettings(name="Test", url="https://api.example.com")
        client = StacClient(conn)
        self.assertFalse(client.is_connected)

    def test_is_connected_false_initially(self):
        """Test that client is not connected initially."""
        conn = ConnectionSettings(name="Test", url="https://api.example.com")
        client = StacClient(conn)
        self.assertFalse(client.is_connected)

    def test_disconnect(self):
        """Test disconnect clears state."""
        conn = ConnectionSettings(name="Test", url="https://api.example.com")
        client = StacClient(conn)
        client._client = Mock()
        client._catalog = Mock()
        self.assertTrue(client.is_connected)

        client.disconnect()
        self.assertFalse(client.is_connected)

    def test_from_settings_raises_without_connection(self):
        """Test from_settings raises when no connection configured."""
        mock_manager = Mock()
        mock_manager.get_connection.return_value = None
        with self.assertRaises(ValueError):
            StacClient.from_settings(mock_manager)

    def test_from_settings_creates_client(self):
        """Test from_settings creates a client from settings."""
        mock_manager = Mock()
        mock_manager.get_connection.return_value = ConnectionSettings(name="Test", url="https://api.example.com")
        client = StacClient.from_settings(mock_manager)
        self.assertIsInstance(client, StacClient)


class TestStacClientOperations(unittest.TestCase):
    """Tests for StacClient operations when not connected."""

    def setUp(self):
        """Set up test client."""
        conn = ConnectionSettings(name="Test", url="https://api.example.com")
        self.client = StacClient(conn)
        self.errors = []
        self.client.error_received.connect(self.errors.append)

    def test_get_catalogs_emits_error_when_not_connected(self):
        """Test get_catalogs emits error when not connected."""
        self.client.get_catalogs()
        self.assertEqual(len(self.errors), 1)
        self.assertIn("Not connected", self.errors[0])

    def test_get_collections_emits_error_when_not_connected(self):
        """Test get_collections emits error when not connected."""
        self.client.get_collections()
        self.assertEqual(len(self.errors), 1)
        self.assertIn("Not connected", self.errors[0])

    def test_search_emits_error_when_not_connected(self):
        """Test search emits error when not connected."""
        self.client.search(SearchFilters())
        self.assertEqual(len(self.errors), 1)
        self.assertIn("Not connected", self.errors[0])

    def test_get_item_returns_none_when_not_connected(self):
        """Test get_item returns None when not connected."""
        result = self.client.get_item("col1", "item1")
        self.assertIsNone(result)
        self.assertEqual(len(self.errors), 1)


class TestStacClientConnected(unittest.TestCase):
    """Tests for StacClient operations when connected."""

    def setUp(self):
        """Set up connected client."""
        conn = ConnectionSettings(name="Test", url="https://api.example.com")
        self.client = StacClient(conn)
        self.client._client = Mock()
        self.client._catalog = Mock()
        self.errors = []
        self.client.error_received.connect(self.errors.append)

    def test_get_catalogs_emits_signal(self):
        """Test get_catalogs emits catalogs_received signal."""
        mock_catalogs = [Mock(), Mock()]
        self.client._catalog.get_catalogs.return_value = mock_catalogs

        received = []
        self.client.catalogs_received.connect(received.append)
        self.client.get_catalogs()

        self.assertEqual(len(received), 1)
        self.assertEqual(len(received[0]), 2)

    def test_get_catalogs_handles_exception(self):
        """Test get_catalogs handles exceptions."""
        self.client._catalog.get_catalogs.side_effect = Exception("Network error")
        self.client.get_catalogs()
        self.assertEqual(len(self.errors), 1)
        self.assertIn("Failed to fetch catalogs", self.errors[0])

    def test_get_collections_emits_signal(self):
        """Test get_collections emits collections_received signal."""
        mock_collections = [Mock()]
        self.client._catalog.get_collections.return_value = mock_collections

        received = []
        self.client.collections_received.connect(received.append)
        self.client.get_collections()

        self.assertEqual(len(received), 1)

    def test_get_collections_with_catalog_id(self):
        """Test get_collections with a specific catalog."""
        mock_catalog = Mock()
        mock_catalog.get_collections.return_value = [Mock()]
        self.client._catalog.get_catalog.return_value = mock_catalog

        received = []
        self.client.collections_received.connect(received.append)
        self.client.get_collections(catalog_id="test-catalog")

        self.client._catalog.get_catalog.assert_called_once_with("test-catalog")
        self.assertEqual(len(received), 1)

    def test_get_collections_handles_exception(self):
        """Test get_collections handles exceptions."""
        self.client._catalog.get_collections.side_effect = Exception("fail")
        self.client.get_collections()
        self.assertEqual(len(self.errors), 1)

    def test_search_emits_items(self):
        """Test search emits items_received signal."""
        mock_item = Mock()
        mock_item.id = "item-1"
        mock_item.collection = "col-1"
        mock_item.datetime = None
        mock_item.bbox = None
        mock_item.geometry = None
        mock_item.properties = {}
        mock_item.assets = {}

        mock_results = [mock_item]
        mock_results_obj = Mock()
        mock_results_obj.__iter__ = Mock(return_value=iter(mock_results))
        mock_results_obj.matched = 1
        self.client._catalog.search.return_value = mock_results_obj

        received = []
        self.client.items_received.connect(lambda items, count: received.append((items, count)))
        self.client.search(SearchFilters(limit=10))

        self.assertEqual(len(received), 1)
        self.assertEqual(len(received[0][0]), 1)
        self.assertEqual(received[0][1], 1)

    def test_search_handles_exception(self):
        """Test search handles exceptions."""
        self.client._catalog.search.side_effect = Exception("search fail")
        self.client.search(SearchFilters())
        self.assertEqual(len(self.errors), 1)
        self.assertIn("Search failed", self.errors[0])

    def test_get_item_returns_item(self):
        """Test get_item returns an ItemResult."""
        mock_item = Mock()
        mock_item.id = "item-1"
        mock_item.collection = "col-1"
        mock_item.datetime = None
        mock_item.bbox = None
        mock_item.geometry = None
        mock_item.properties = {}
        mock_item.assets = {}

        mock_collection = Mock()
        mock_collection.get_item.return_value = mock_item
        self.client._catalog.get_collection.return_value = mock_collection

        result = self.client.get_item("col-1", "item-1")
        self.assertIsNotNone(result)
        self.assertEqual(result.id, "item-1")

    def test_get_item_handles_exception(self):
        """Test get_item handles exceptions."""
        self.client._catalog.get_collection.side_effect = Exception("not found")
        result = self.client.get_item("col-1", "item-1")
        self.assertIsNone(result)
        self.assertEqual(len(self.errors), 1)


if __name__ == "__main__":
    unittest.main()
