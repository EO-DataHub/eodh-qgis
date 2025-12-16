"""Data models for STAC API objects using dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ConnectionSettings:
    """STAC connection configuration.

    Attributes:
        name: Display name for the connection
        url: Base URL of the STAC API
        auth_config_id: Optional QGIS authentication config ID
        environment: Environment name (e.g., "production", "staging")
    """

    name: str
    url: str
    auth_config_id: str | None = None
    environment: str = "production"


@dataclass
class SearchFilters:
    """Search filter parameters for STAC queries.

    Attributes:
        bbox: Bounding box as (west, south, east, north)
        start_date: Start of date range filter
        end_date: End of date range filter
        collections: List of collection IDs to search
        limit: Maximum number of results per page
    """

    bbox: tuple[float, float, float, float] | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    collections: list[str] = field(default_factory=list)
    limit: int = 50

    def to_search_params(self) -> dict[str, Any]:
        """Convert to parameters dict for STAC search API.

        Returns:
            Dictionary of search parameters suitable for pyeodh/pystac search
        """
        params: dict[str, Any] = {"limit": self.limit}

        if self.bbox:
            params["bbox"] = list(self.bbox)

        if self.start_date or self.end_date:
            start = self.start_date.isoformat() if self.start_date else ".."
            end = self.end_date.isoformat() if self.end_date else ".."
            params["datetime"] = f"{start}/{end}"

        if self.collections:
            params["collections"] = self.collections

        return params


@dataclass
class AssetInfo:
    """Asset metadata for display and loading.

    Attributes:
        key: Asset key in the item's assets dictionary
        href: URL or path to the asset
        file_type: Human-readable file type (e.g., "GeoTIFF", "NetCDF")
        epsg: EPSG code if known (e.g., "4326")
        roles: List of STAC asset roles
        media_type: MIME type of the asset
    """

    key: str
    href: str
    file_type: str
    epsg: str | None = None
    roles: list[str] = field(default_factory=list)
    media_type: str | None = None

    @classmethod
    def from_stac_asset(cls, key: str, asset) -> AssetInfo:
        """Create AssetInfo from a STAC asset object.

        Args:
            key: Asset key name
            asset: STAC asset object (from pystac/pyeodh)

        Returns:
            AssetInfo instance with extracted metadata
        """
        from eodh_qgis.asset_utils import extract_epsg_from_asset, get_asset_file_type

        return cls(
            key=key,
            href=getattr(asset, "href", ""),
            file_type=get_asset_file_type(asset),
            epsg=extract_epsg_from_asset(asset),
            roles=getattr(asset, "roles", []) or [],
            media_type=getattr(asset, "type", None),
        )


@dataclass
class ItemResult:
    """Simplified STAC item for display purposes.

    Attributes:
        id: Unique item identifier
        collection: Collection ID this item belongs to
        datetime: Item's datetime (acquisition time)
        bbox: Bounding box as (west, south, east, north)
        geometry: GeoJSON geometry dict
        assets: Dictionary mapping asset keys to AssetInfo objects
        properties: Additional item properties
    """

    id: str
    collection: str | None = None
    datetime: datetime | None = None
    bbox: tuple[float, float, float, float] | None = None
    geometry: dict | None = None
    assets: dict[str, AssetInfo] = field(default_factory=dict)
    properties: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_stac_item(cls, item) -> ItemResult:
        """Create ItemResult from a STAC item object.

        Args:
            item: STAC item object (from pystac/pyeodh)

        Returns:
            ItemResult instance with extracted data
        """
        # Extract assets
        assets = {}
        if hasattr(item, "assets") and item.assets:
            for key, asset in item.assets.items():
                assets[key] = AssetInfo.from_stac_asset(key, asset)

        # Extract bbox
        bbox = None
        if hasattr(item, "bbox") and item.bbox and len(item.bbox) == 4:
            bbox = tuple(item.bbox)

        # Extract datetime
        dt = None
        if hasattr(item, "datetime") and item.datetime:
            if isinstance(item.datetime, datetime):
                dt = item.datetime
            elif isinstance(item.datetime, str):
                try:
                    dt = datetime.fromisoformat(item.datetime.replace("Z", "+00:00"))
                except ValueError:
                    pass

        return cls(
            id=str(item.id),
            collection=str(item.collection) if item.collection else None,
            datetime=dt,
            bbox=bbox,
            geometry=getattr(item, "geometry", None),
            assets=assets,
            properties=getattr(item, "properties", {}) or {},
        )

    def has_geometry(self) -> bool:
        """Check if this item has valid geometry."""
        return self.geometry is not None
