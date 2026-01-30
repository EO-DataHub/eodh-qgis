"""Layer creation utilities for STAC items and assets."""

from __future__ import annotations

import tempfile
import urllib.request

from osgeo import gdal, osr
from qgis.core import Qgis, QgsMessageLog, QgsRasterLayer

from eodh_qgis.definitions.constants import (
    COG_MIME_TYPES,
    NETCDF_MIME_TYPES,
    PLUGIN_NAME,
)
from eodh_qgis.utils import get_netcdf_metadata


def download_with_progress(url: str, dest_path: str, callback=None):
    """Download file with progress callback.

    Args:
        url: URL to download from
        dest_path: Local file path to save to
        callback: Optional callback function(percent: int) for progress updates.
            Throttled to update every 2% to avoid UI overhead.
    """
    last_percent = -1

    def reporthook(block_num, block_size, total_size):
        nonlocal last_percent
        if callback and total_size > 0:
            percent = min(100, int(block_num * block_size * 100 / total_size))
            # Only update every 2% to avoid excessive UI overhead
            # (urllib calls this ~12,000 times for 100MB file)
            if percent >= last_percent + 2:
                last_percent = percent
                callback(percent)

    urllib.request.urlretrieve(url, dest_path, reporthook=reporthook)


def create_layers_for_asset(
    item,
    asset_key: str,
    asset,
    selected_variables: list[str] | None = None,
    progress_callback=None,
) -> list[QgsRasterLayer]:
    """Create QGIS raster layer(s) for a single STAC asset.

    For NetCDF files with multiple data variables, each variable is returned
    as a separate layer.

    Args:
        item: STAC item object (used for naming)
        asset_key: Key name of the asset in item.assets
        asset: STAC asset object with 'href' and optional 'type'
        selected_variables: Optional list of variable names to load (NetCDF only).
            If None, all data variables are loaded.
        progress_callback: Optional callback function(percent: int) for download
            progress updates (0-100).

    Returns:
        List of valid QgsRasterLayer objects
    """
    url = asset.href
    asset_type = getattr(asset, "type", "") or ""

    # Check if this is a NetCDF file
    is_netcdf = any(
        nc_type in asset_type for nc_type in NETCDF_MIME_TYPES
    ) or url.endswith(".nc")

    # For NetCDF, download to temp file first (geolocation warp requires local file)
    if is_netcdf and url.startswith("http"):
        QgsMessageLog.logMessage(
            f"Downloading NetCDF file: {url[:80]}...",
            PLUGIN_NAME,
            level=Qgis.Info,
        )
        try:
            temp_file = tempfile.NamedTemporaryFile(suffix=".nc", delete=False)
            download_with_progress(url, temp_file.name, progress_callback)
            url = temp_file.name
            QgsMessageLog.logMessage(
                f"NetCDF downloaded to: {url}",
                PLUGIN_NAME,
                level=Qgis.Info,
            )
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Failed to download NetCDF: {e}",
                PLUGIN_NAME,
                level=Qgis.Warning,
            )
            return []

    # Use /vsicurl/ for remote streaming of COG/GeoTIFF (not NetCDF)
    needs_vsicurl = (
        any(cog_type in asset_type for cog_type in COG_MIME_TYPES)
        or url.endswith(".tif")
        or url.endswith(".tiff")
    )
    if needs_vsicurl and url.startswith("http"):
        url = f"/vsicurl/{url}"

    layer_name = f"{item.id}_{asset_key}"
    QgsMessageLog.logMessage(
        f"Creating layer(s) '{layer_name}' from: {url[:80]}...",
        PLUGIN_NAME,
        level=Qgis.Info,
    )

    # For NetCDF, try to load data variables
    if is_netcdf:
        layers = get_netcdf_layers(url, layer_name, selected_variables)
        if layers:
            return layers
        # If no layers from subdatasets, fall through to try direct load

    # Try direct load for non-NetCDF or NetCDF without subdatasets
    layer = QgsRasterLayer(url, layer_name)

    if not layer.isValid():
        error_msg = layer.error().message() if layer else "Unknown error"
        QgsMessageLog.logMessage(
            f"Layer invalid for {asset_key}: {error_msg}",
            PLUGIN_NAME,
            level=Qgis.Warning,
        )
        return []

    return [layer]


def get_netcdf_layers(
    url: str,
    layer_name: str,
    selected_variables: list[str] | None = None,
) -> list[QgsRasterLayer]:
    """Get data variable layers from a NetCDF file.

    Uses CF convention attributes to skip coordinate variables and load
    data variables as separate layers. Applies georeferencing from
    xc/yc coordinate arrays if available.

    Args:
        url: Path to NetCDF file (local path, not vsicurl)
        layer_name: Base name for the layers
        selected_variables: If provided, only load these variables.
            If None, load all data variables.

    Returns:
        List of valid QgsRasterLayer objects for each data variable
    """
    layers = []
    try:
        # Get all metadata in ONE consolidated call (2 file opens instead of 4)
        metadata = get_netcdf_metadata(url)
        data_vars = metadata.data_variables
        geotransform = metadata.geotransform
        epsg = metadata.epsg

        # Filter to selected variables if specified
        if selected_variables is not None:
            data_vars = [
                (uri, name) for uri, name in data_vars if name in selected_variables
            ]

        if not data_vars:
            QgsMessageLog.logMessage(
                f"NetCDF has no loadable data variables: {url[:80]}...",
                PLUGIN_NAME,
                level=Qgis.Warning,
            )
            return layers

        QgsMessageLog.logMessage(
            f"NetCDF has {len(data_vars)} data variables to load",
            PLUGIN_NAME,
            level=Qgis.Info,
        )

        if geotransform and epsg:
            QgsMessageLog.logMessage(
                f"NetCDF geotransform from xc/yc: {geotransform}, EPSG:{epsg}",
                PLUGIN_NAME,
                level=Qgis.Info,
            )

        for subdataset_uri, var_name in data_vars:
            QgsMessageLog.logMessage(
                f"Loading NetCDF variable: {var_name}",
                PLUGIN_NAME,
                level=Qgis.Info,
            )

            layer = None
            if geotransform and epsg:
                # Create VRT with proper georeferencing using gdal.Translate
                vrt_path = f"/vsimem/{layer_name}_{var_name}.vrt"
                src_ds = gdal.Open(subdataset_uri)

                if src_ds:
                    vrt_ds = gdal.Translate(vrt_path, src_ds, format="VRT")
                    if vrt_ds:
                        vrt_ds.SetGeoTransform(geotransform)
                        # Use proper WKT projection (SetProjection needs WKT)
                        srs = osr.SpatialReference()
                        srs.ImportFromEPSG(int(epsg))
                        vrt_ds.SetProjection(srs.ExportToWkt())
                        vrt_ds.FlushCache()
                        vrt_ds = None
                        src_ds = None

                        layer = QgsRasterLayer(vrt_path, f"{layer_name}_{var_name}")
                        if layer.isValid():
                            QgsMessageLog.logMessage(
                                f"Created georeferenced layer for {var_name} "
                                f"with EPSG:{epsg}",
                                PLUGIN_NAME,
                                level=Qgis.Info,
                            )

            if not layer or not layer.isValid():
                # Fallback to direct load without georeferencing
                QgsMessageLog.logMessage(
                    f"Georeferencing failed for {var_name}, trying direct load",
                    PLUGIN_NAME,
                    level=Qgis.Warning,
                )
                layer = QgsRasterLayer(subdataset_uri, f"{layer_name}_{var_name}")

            if layer and layer.isValid():
                layers.append(layer)
            else:
                QgsMessageLog.logMessage(
                    f"Failed to load NetCDF variable {var_name}: "
                    f"{layer.error().message() if layer else 'Unknown error'}",
                    PLUGIN_NAME,
                    level=Qgis.Warning,
                )

    except Exception as e:
        QgsMessageLog.logMessage(
            f"Error reading NetCDF variables: {e}",
            PLUGIN_NAME,
            level=Qgis.Warning,
        )
    return layers
