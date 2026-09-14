"""API module for STAC client and data models."""

from .models import AssetInfo, ConnectionSettings, ItemResult, SearchFilters


def __getattr__(name):
    if name == "StacClient":
        from .client import StacClient

        return StacClient
    raise AttributeError(name)


__all__ = [
    "AssetInfo",
    "ConnectionSettings",
    "ItemResult",
    "SearchFilters",
    "StacClient",
]
