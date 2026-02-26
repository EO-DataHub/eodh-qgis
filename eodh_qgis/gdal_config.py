"""GDAL virtual file system configuration for optimal remote raster streaming.

Sets GDAL configuration options that improve /vsicurl/ performance for
remote raster loading. Without these options, GDAL's default behavior
causes excessive HTTP requests (sidecar file probing) and high latency.

Options are applied when the plugin loads and restored when it unloads,
to avoid affecting other QGIS plugins.
"""

from __future__ import annotations

from osgeo import gdal
from qgis.core import Qgis, QgsMessageLog

from eodh_qgis.definitions.constants import PLUGIN_NAME

# GDAL vsicurl performance options for remote raster streaming.
GDAL_VSICURL_OPTIONS: dict[str, str] = {
    # Prevent directory listing for sidecar files (.aux.xml, .ovr, .prj).
    # Single biggest performance win — eliminates 3-5 extra HTTP requests per open.
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    # Enable RAM caching of fetched byte ranges.
    "VSI_CACHE": "TRUE",
    # Cache size: 50 MB (default ~25 MB).
    "VSI_CACHE_SIZE": "52428800",
    # Only fetch files with these extensions via curl (blocks sidecar probing).
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.tiff,.png,.jpg,.jpeg",
    # Combine multiple byte-range requests into one HTTP request.
    "GDAL_HTTP_MULTIRANGE": "YES",
    # Merge adjacent byte ranges.
    "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
    # Retry on transient HTTP failures.
    "GDAL_HTTP_MAX_RETRY": "3",
    "GDAL_HTTP_RETRY_DELAY": "1",
}

# Stores previous values for restore on unload.
_previous_values: dict[str, str | None] = {}


def configure_gdal_vsicurl() -> None:
    """Set GDAL config options for optimal vsicurl performance.

    Saves current values before overwriting so they can be restored
    with restore_gdal_vsicurl(). Call once during plugin initGui().
    """
    global _previous_values
    _previous_values = {}

    for key, value in GDAL_VSICURL_OPTIONS.items():
        _previous_values[key] = gdal.GetConfigOption(key)
        gdal.SetConfigOption(key, value)

    QgsMessageLog.logMessage(
        f"GDAL vsicurl configuration applied ({len(GDAL_VSICURL_OPTIONS)} options)",
        PLUGIN_NAME,
        level=Qgis.Info,
    )


def restore_gdal_vsicurl() -> None:
    """Restore GDAL config options to their previous values.

    Call during plugin unload() to be a good citizen.
    """
    for key, previous_value in _previous_values.items():
        gdal.SetConfigOption(key, previous_value)

    _previous_values.clear()

    QgsMessageLog.logMessage(
        "GDAL vsicurl configuration restored",
        PLUGIN_NAME,
        level=Qgis.Info,
    )
