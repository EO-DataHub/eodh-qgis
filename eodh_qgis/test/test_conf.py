"""Tests for settings management."""

import unittest

from qgis.core import QgsSettings

from eodh_qgis.api.models import ConnectionSettings, SearchFilters
from eodh_qgis.conf import SettingsManager, qgis_settings


class TestQgisSettingsContextManager(unittest.TestCase):
    """Tests for qgis_settings context manager."""

    def setUp(self):
        """Clear test settings before each test."""
        s = QgsSettings()
        s.beginGroup("eodh_qgis_test")
        s.remove("")
        s.endGroup()

    def test_context_manager_opens_and_closes_group(self):
        """Test that group is properly entered and exited."""
        with qgis_settings("eodh_qgis_test") as s:
            s.setValue("key1", "value1")

        # Verify value was saved in the right group
        s = QgsSettings()
        s.beginGroup("eodh_qgis_test")
        self.assertEqual(s.value("key1"), "value1")
        s.endGroup()

    def test_context_manager_with_existing_settings(self):
        """Test passing an existing QgsSettings instance."""
        existing = QgsSettings()
        with qgis_settings("eodh_qgis_test", existing) as s:
            s.setValue("key2", "value2")

        existing.beginGroup("eodh_qgis_test")
        self.assertEqual(existing.value("key2"), "value2")
        existing.endGroup()


class TestSettingsManager(unittest.TestCase):
    """Tests for SettingsManager class."""

    def setUp(self):
        """Clear plugin settings before each test."""
        self.manager = SettingsManager()
        self.manager.clear_all()

    def tearDown(self):
        """Clean up after tests."""
        self.manager.clear_all()

    def test_get_connection_returns_none_when_empty(self):
        """Test that get_connection returns None with no saved connection."""
        conn = self.manager.get_connection()
        self.assertIsNone(conn)

    def test_save_and_get_connection(self):
        """Test saving and retrieving a connection."""
        conn = ConnectionSettings(
            name="Test",
            url="https://api.example.com",
            auth_config_id="abc123",
            environment="staging",
        )
        self.manager.save_connection(conn)

        result = self.manager.get_connection()
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "Test")
        self.assertEqual(result.url, "https://api.example.com")
        self.assertEqual(result.auth_config_id, "abc123")
        self.assertEqual(result.environment, "staging")

    def test_save_and_get_auth_config(self):
        """Test saving and retrieving auth config."""
        self.manager.save_auth_config("my-auth-id")
        self.assertEqual(self.manager.get_auth_config(), "my-auth-id")

    def test_get_auth_config_default(self):
        """Test default auth config is empty string."""
        self.assertEqual(self.manager.get_auth_config(), "")

    def test_save_and_get_environment(self):
        """Test saving and retrieving environment."""
        self.manager.save_environment("staging")
        self.assertEqual(self.manager.get_environment(), "staging")

    def test_get_environment_default(self):
        """Test default environment is production."""
        self.assertEqual(self.manager.get_environment(), "production")

    def test_save_and_get_page_size(self):
        """Test saving and retrieving page size."""
        self.manager.save_page_size(25)
        self.assertEqual(self.manager.get_page_size(), 25)

    def test_get_page_size_default(self):
        """Test default page size."""
        from eodh_qgis.definitions.constants import DEFAULT_PAGE_SIZE

        self.assertEqual(self.manager.get_page_size(), DEFAULT_PAGE_SIZE)

    def test_save_and_get_search_filters_with_bbox(self):
        """Test saving and retrieving search filters with bbox."""
        filters = SearchFilters(
            bbox=(-10.0, 45.0, 20.0, 60.0),
            collections=["col1", "col2"],
            limit=25,
        )
        self.manager.save_search_filters(filters)

        result = self.manager.get_search_filters()
        self.assertEqual(result.bbox, (-10.0, 45.0, 20.0, 60.0))
        self.assertEqual(result.collections, ["col1", "col2"])

    def test_save_and_get_search_filters_empty(self):
        """Test saving filters with no bbox or collections."""
        filters = SearchFilters(limit=10)
        self.manager.save_search_filters(filters)

        result = self.manager.get_search_filters()
        self.assertIsNone(result.bbox)
        self.assertEqual(result.collections, [])

    def test_get_search_filters_invalid_bbox(self):
        """Test that invalid bbox string is handled gracefully."""
        with qgis_settings("eodh_qgis") as s:
            s.setValue("last_bbox", "not,a,valid")

        result = self.manager.get_search_filters()
        self.assertIsNone(result.bbox)

    def test_clear_all(self):
        """Test clearing all settings."""
        self.manager.save_environment("staging")
        self.manager.save_page_size(99)
        self.manager.clear_all()

        self.assertEqual(self.manager.get_environment(), "production")

    def test_connection_without_auth(self):
        """Test saving connection without auth config."""
        conn = ConnectionSettings(
            name="No Auth",
            url="https://api.example.com",
        )
        self.manager.save_connection(conn)

        result = self.manager.get_connection()
        self.assertIsNone(result.auth_config_id)


if __name__ == "__main__":
    unittest.main()
