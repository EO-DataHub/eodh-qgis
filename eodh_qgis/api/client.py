"""STAC API client with Qt signals for async operations."""

from __future__ import annotations

from typing import Any

from qgis.core import Qgis, QgsMessageLog
from qgis.PyQt import QtCore

from eodh_qgis.api.models import ConnectionSettings, ItemResult, SearchFilters
from eodh_qgis.definitions.constants import PLUGIN_NAME


class StacClient(QtCore.QObject):
    """STAC API client with Qt signals for async operations.

    Wraps pyeodh client to provide Qt-compatible signal-based API
    for use in QGIS GUI components.

    Signals:
        catalogs_received: Emitted when catalogs are fetched
            (list of catalog objects)
        collections_received: Emitted when collections are fetched
            (list of collection objects)
        items_received: Emitted when search results arrive
            (list of ItemResult, total_count)
        error_received: Emitted when an error occurs (error message string)

    Usage:
        client = StacClient(connection_settings)
        client.items_received.connect(self._on_items_received)
        client.error_received.connect(self._on_error)

        if client.connect():
            client.search(search_filters)
    """

    # Signals for async responses
    catalogs_received = QtCore.pyqtSignal(list)
    collections_received = QtCore.pyqtSignal(list)
    items_received = QtCore.pyqtSignal(list, int)  # items, total_count
    error_received = QtCore.pyqtSignal(str)

    def __init__(self, connection: ConnectionSettings, parent: QtCore.QObject | None = None) -> None:
        """Initialize the STAC client.

        Args:
            connection: Connection settings including URL and auth config
            parent: Optional Qt parent object
        """
        super().__init__(parent)
        self._connection = connection
        self._client: Any = None
        self._catalog: Any = None

    @property
    def is_connected(self) -> bool:
        """Check if client is connected to STAC API."""
        return self._client is not None and self._catalog is not None

    @classmethod
    def from_settings(cls, settings_manager, parent: QtCore.QObject | None = None) -> StacClient:
        """Create a StacClient from the settings manager.

        Args:
            settings_manager: SettingsManager instance with connection config
            parent: Optional Qt parent object

        Returns:
            StacClient instance configured from settings

        Raises:
            ValueError: If no connection is configured
        """
        conn = settings_manager.get_connection()
        if conn is None:
            raise ValueError("No connection configured in settings")
        return cls(conn, parent)

    def connect(self) -> bool:
        """Initialize connection to STAC API.

        Returns:
            True if connection was successful, False otherwise
        """
        try:
            from pyeodh import Client as PyeodhClient

            QgsMessageLog.logMessage(
                f"Connecting to STAC API: {self._connection.url}",
                PLUGIN_NAME,
                level=Qgis.Info,
            )

            self._client = PyeodhClient(
                url=self._connection.url,  # type: ignore[call-arg]
                # Add auth config if available
            )
            self._catalog = self._client.get_catalog_service()

            QgsMessageLog.logMessage(
                "Successfully connected to STAC API",
                PLUGIN_NAME,
                level=Qgis.Info,
            )
            return True

        except Exception as e:
            error_msg = f"Failed to connect to STAC API: {e}"
            QgsMessageLog.logMessage(error_msg, PLUGIN_NAME, level=Qgis.Warning)
            self.error_received.emit(error_msg)
            return False

    def disconnect(self) -> None:
        """Disconnect from the STAC API."""
        self._client = None
        self._catalog = None

    def get_catalogs(self) -> None:
        """Fetch available catalogs (async via signal)."""
        if not self.is_connected:
            self.error_received.emit("Not connected to STAC API")
            return

        try:
            catalogs = list(self._catalog.get_catalogs())
            self.catalogs_received.emit(catalogs)
        except Exception as e:
            error_msg = f"Failed to fetch catalogs: {e}"
            QgsMessageLog.logMessage(error_msg, PLUGIN_NAME, level=Qgis.Warning)
            self.error_received.emit(error_msg)

    def get_collections(self, catalog_id: str | None = None) -> None:
        """Fetch collections for a catalog.

        Args:
            catalog_id: Optional catalog ID to filter collections
        """
        if not self.is_connected:
            self.error_received.emit("Not connected to STAC API")
            return

        try:
            # Get the catalog object
            if catalog_id:
                catalog = self._catalog.get_catalog(catalog_id)
                collections = list(catalog.get_collections())
            else:
                collections = list(self._catalog.get_collections())

            self.collections_received.emit(collections)
        except Exception as e:
            error_msg = f"Failed to fetch collections: {e}"
            QgsMessageLog.logMessage(error_msg, PLUGIN_NAME, level=Qgis.Warning)
            self.error_received.emit(error_msg)

    def search(self, filters: SearchFilters) -> None:
        """Execute STAC search with filters.

        Results are emitted via the items_received signal.

        Args:
            filters: SearchFilters with query parameters
        """
        if not self.is_connected:
            self.error_received.emit("Not connected to STAC API")
            return

        try:
            params = filters.to_search_params()

            QgsMessageLog.logMessage(
                f"Searching STAC API with params: {params}",
                PLUGIN_NAME,
                level=Qgis.Info,
            )

            # Execute search
            results = self._catalog.search(**params)

            # Convert to ItemResult objects
            items = [ItemResult.from_stac_item(item) for item in results]

            # Get total count if available
            total_count = getattr(results, "matched", len(items))
            if total_count is None:
                total_count = len(items)

            QgsMessageLog.logMessage(
                f"Search returned {len(items)} items (total: {total_count})",
                PLUGIN_NAME,
                level=Qgis.Info,
            )

            self.items_received.emit(items, total_count)

        except Exception as e:
            error_msg = f"Search failed: {e}"
            QgsMessageLog.logMessage(error_msg, PLUGIN_NAME, level=Qgis.Warning)
            self.error_received.emit(error_msg)

    def get_item(self, collection_id: str, item_id: str) -> ItemResult | None:
        """Fetch a single item by ID.

        Args:
            collection_id: Collection containing the item
            item_id: ID of the item to fetch

        Returns:
            ItemResult if found, None on error
        """
        if not self.is_connected:
            self.error_received.emit("Not connected to STAC API")
            return None

        try:
            collection = self._catalog.get_collection(collection_id)
            item = collection.get_item(item_id)
            return ItemResult.from_stac_item(item)
        except Exception as e:
            error_msg = f"Failed to fetch item {item_id}: {e}"
            QgsMessageLog.logMessage(error_msg, PLUGIN_NAME, level=Qgis.Warning)
            self.error_received.emit(error_msg)
            return None
