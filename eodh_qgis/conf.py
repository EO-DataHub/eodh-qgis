"""Enhanced settings management for EODH QGIS plugin."""

from __future__ import annotations

import contextlib
from typing import Generator

from qgis.core import QgsSettings

from eodh_qgis.api.models import ConnectionSettings, SearchFilters
from eodh_qgis.definitions.constants import DEFAULT_PAGE_SIZE, PLUGIN_NAME


@contextlib.contextmanager
def qgis_settings(
    group: str, settings: QgsSettings | None = None
) -> Generator[QgsSettings, None, None]:
    """Context manager for safe QgsSettings group management.

    Automatically handles beginGroup/endGroup to prevent group nesting issues.

    Args:
        group: Settings group path (e.g., "eodh_qgis/connection")
        settings: Optional existing QgsSettings instance

    Yields:
        QgsSettings instance with the group already begun
    """
    if settings is None:
        settings = QgsSettings()
    assert settings is not None
    settings.beginGroup(group)
    try:
        yield settings
    finally:
        settings.endGroup()


class SettingsManager:
    """Centralized settings management using QgsSettings.

    Provides typed access to plugin settings with dataclass integration.
    Uses context managers for safe settings group handling.

    Usage:
        from eodh_qgis.conf import settings_manager

        # Get current connection
        conn = settings_manager.get_connection()

        # Save a connection
        settings_manager.save_connection(ConnectionSettings(
            name="My Connection",
            url="https://api.example.com"
        ))
    """

    PLUGIN_GROUP = "eodh_qgis"

    # Keys for settings
    KEY_AUTH_CONFIG = "auth_config"
    KEY_ENVIRONMENT = "env"
    KEY_CONNECTION_NAME = "connection_name"
    KEY_CONNECTION_URL = "connection_url"
    KEY_LAST_BBOX = "last_bbox"
    KEY_LAST_COLLECTIONS = "last_collections"
    KEY_PAGE_SIZE = "page_size"

    def __init__(self) -> None:
        """Initialize the settings manager."""
        self._settings = QgsSettings()

    def get_connection(self) -> ConnectionSettings | None:
        """Get current connection settings.

        Returns:
            ConnectionSettings if configured, None otherwise
        """
        with qgis_settings(self.PLUGIN_GROUP, self._settings) as s:
            url = s.value(self.KEY_CONNECTION_URL, "")
            if not url:
                return None

            return ConnectionSettings(
                name=s.value(self.KEY_CONNECTION_NAME, PLUGIN_NAME),
                url=url,
                auth_config_id=s.value(self.KEY_AUTH_CONFIG) or None,
                environment=s.value(self.KEY_ENVIRONMENT, "production"),
            )

    def save_connection(self, conn: ConnectionSettings) -> None:
        """Save connection settings.

        Args:
            conn: Connection settings to save
        """
        with qgis_settings(self.PLUGIN_GROUP, self._settings) as s:
            s.setValue(self.KEY_CONNECTION_NAME, conn.name)
            s.setValue(self.KEY_CONNECTION_URL, conn.url)
            s.setValue(self.KEY_AUTH_CONFIG, conn.auth_config_id or "")
            s.setValue(self.KEY_ENVIRONMENT, conn.environment)

    def get_auth_config(self) -> str:
        """Get the authentication configuration ID.

        Returns:
            Auth config ID or empty string if not set
        """
        with qgis_settings(self.PLUGIN_GROUP, self._settings) as s:
            return s.value(self.KEY_AUTH_CONFIG, "")

    def save_auth_config(self, auth_config_id: str) -> None:
        """Save authentication configuration ID.

        Args:
            auth_config_id: QGIS authentication config ID
        """
        with qgis_settings(self.PLUGIN_GROUP, self._settings) as s:
            s.setValue(self.KEY_AUTH_CONFIG, auth_config_id)

    def get_environment(self) -> str:
        """Get the environment setting.

        Returns:
            Environment name (default: "production")
        """
        with qgis_settings(self.PLUGIN_GROUP, self._settings) as s:
            return s.value(self.KEY_ENVIRONMENT, "production")

    def save_environment(self, environment: str) -> None:
        """Save environment setting.

        Args:
            environment: Environment name (e.g., "production", "staging")
        """
        with qgis_settings(self.PLUGIN_GROUP, self._settings) as s:
            s.setValue(self.KEY_ENVIRONMENT, environment)

    def get_page_size(self) -> int:
        """Get the default page size for search results.

        Returns:
            Page size (default: DEFAULT_PAGE_SIZE)
        """
        with qgis_settings(self.PLUGIN_GROUP, self._settings) as s:
            return int(s.value(self.KEY_PAGE_SIZE, DEFAULT_PAGE_SIZE))

    def save_page_size(self, page_size: int) -> None:
        """Save the default page size.

        Args:
            page_size: Number of results per page
        """
        with qgis_settings(self.PLUGIN_GROUP, self._settings) as s:
            s.setValue(self.KEY_PAGE_SIZE, page_size)

    def get_search_filters(self) -> SearchFilters:
        """Get last used search filters.

        Returns:
            SearchFilters with last used values or defaults
        """
        with qgis_settings(self.PLUGIN_GROUP, self._settings) as s:
            # Parse bbox
            bbox = None
            bbox_str = s.value(self.KEY_LAST_BBOX, "")
            if bbox_str:
                try:
                    parts = [float(x) for x in bbox_str.split(",")]
                    if len(parts) == 4:
                        bbox = (parts[0], parts[1], parts[2], parts[3])
                except ValueError:
                    pass

            # Parse collections
            collections = []
            collections_str = s.value(self.KEY_LAST_COLLECTIONS, "")
            if collections_str:
                collections = [
                    c.strip() for c in collections_str.split(",") if c.strip()
                ]

            return SearchFilters(
                bbox=bbox,
                collections=collections,
                limit=self.get_page_size(),
            )

    def save_search_filters(self, filters: SearchFilters) -> None:
        """Save search filters for next session.

        Args:
            filters: SearchFilters to save
        """
        with qgis_settings(self.PLUGIN_GROUP, self._settings) as s:
            # Save bbox
            if filters.bbox:
                bbox_str = ",".join(str(x) for x in filters.bbox)
                s.setValue(self.KEY_LAST_BBOX, bbox_str)
            else:
                s.setValue(self.KEY_LAST_BBOX, "")

            # Save collections
            if filters.collections:
                s.setValue(self.KEY_LAST_COLLECTIONS, ",".join(filters.collections))
            else:
                s.setValue(self.KEY_LAST_COLLECTIONS, "")

            # Save page size
            s.setValue(self.KEY_PAGE_SIZE, filters.limit)

    def clear_all(self) -> None:
        """Clear all plugin settings."""
        with qgis_settings(self.PLUGIN_GROUP, self._settings) as s:
            s.remove("")  # Removes all keys in the group


# Module-level singleton for easy access
settings_manager = SettingsManager()
