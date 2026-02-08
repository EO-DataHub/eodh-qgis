"""Definitions module for EODH QGIS plugin constants and enums."""

from .asset_types import AssetLayerType, AssetRole
from .constants import (
    DEFAULT_PAGE_SIZE,
    LOADABLE_EXTENSIONS,
    LOADABLE_MIME_TYPES,
    PLUGIN_NAME,
    THUMBNAIL_SIZE,
)

__all__ = [
    "DEFAULT_PAGE_SIZE",
    "LOADABLE_EXTENSIONS",
    "LOADABLE_MIME_TYPES",
    "PLUGIN_NAME",
    "THUMBNAIL_SIZE",
    "AssetLayerType",
    "AssetRole",
]
