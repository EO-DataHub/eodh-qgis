"""NetCDF layer creation used by the current raster loader."""

from __future__ import annotations

from osgeo import gdal, osr
from qgis.core import Qgis, QgsMessageLog, QgsRasterLayer

from eodh_qgis.definitions.constants import PLUGIN_NAME
from eodh_qgis.utils import get_netcdf_metadata


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
            data_vars = [(uri, name) for uri, name in data_vars if name in selected_variables]

        if not data_vars:
            QgsMessageLog.logMessage(
                f"NetCDF has no loadable data variables: {url[:80]}...",
                PLUGIN_NAME,
                level=Qgis.MessageLevel.Warning,
            )
            return layers

        QgsMessageLog.logMessage(
            f"NetCDF has {len(data_vars)} data variables to load",
            PLUGIN_NAME,
            level=Qgis.MessageLevel.Info,
        )

        if geotransform and epsg:
            QgsMessageLog.logMessage(
                f"NetCDF geotransform from xc/yc: {geotransform}, EPSG:{epsg}",
                PLUGIN_NAME,
                level=Qgis.MessageLevel.Info,
            )

        for subdataset_uri, var_name in data_vars:
            QgsMessageLog.logMessage(
                f"Loading NetCDF variable: {var_name}",
                PLUGIN_NAME,
                level=Qgis.MessageLevel.Info,
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
                                f"Created georeferenced layer for {var_name} with EPSG:{epsg}",
                                PLUGIN_NAME,
                                level=Qgis.MessageLevel.Info,
                            )

            if not layer or not layer.isValid():
                # Fallback to direct load without georeferencing
                QgsMessageLog.logMessage(
                    f"Georeferencing failed for {var_name}, trying direct load",
                    PLUGIN_NAME,
                    level=Qgis.MessageLevel.Warning,
                )
                layer = QgsRasterLayer(subdataset_uri, f"{layer_name}_{var_name}")

            if layer and layer.isValid():
                layers.append(layer)
            else:
                QgsMessageLog.logMessage(
                    f"Failed to load NetCDF variable {var_name}: "
                    f"{layer.error().message() if layer else 'Unknown error'}",
                    PLUGIN_NAME,
                    level=Qgis.MessageLevel.Warning,
                )

    except Exception as e:
        QgsMessageLog.logMessage(
            f"Error reading NetCDF variables: {e}",
            PLUGIN_NAME,
            level=Qgis.MessageLevel.Warning,
        )
    return layers
