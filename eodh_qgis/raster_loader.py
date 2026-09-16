"""Open remote rasters using GDAL range reads, without persisting API keys."""

import tempfile
from pathlib import Path
from urllib.parse import quote, urlsplit

from osgeo import gdal
from qgis.core import QgsRasterLayer

from eodh_qgis.api.hub import HubError, asset_type

# GDAL render workers need these options after the loading task has finished.
# They are scoped to each exact source, never to the whole QGIS process.
_authenticated_sources = set()


class StreamingUnavailable(HubError):
    """The loading task should fall back to downloading the complete file."""


def streaming_source(client, url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise HubError("EODH links must use HTTPS without embedded credentials.")
    source = "/vsicurl?empty_dir=yes&use_head=no&url=" + quote(url, safe="")
    options = {
        "GDAL_HTTP_CONNECTTIMEOUT": "10",
        "GDAL_HTTP_TIMEOUT": "45",
        "GDAL_HTTP_MAX_RETRY": "2",
        "GDAL_HTTP_RETRY_DELAY": "1",
        "GDAL_HTTP_MULTIPLEX": "YES",
        "CPL_VSIL_CURL_AUTHORIZATION_HEADER_ALLOWED_IF_REDIRECT": "SAME_HOST",
    }
    if parsed.netloc == urlsplit(client.base).netloc:
        options["GDAL_HTTP_HEADERS"] = "Authorization: Bearer " + client.token
        _authenticated_sources.add(source)
    for key, value in options.items():
        gdal.SetPathSpecificOption(source, key, value)
    return source


def clear_stream_credentials():
    for source in _authenticated_sources:
        gdal.SetPathSpecificOption(source, "GDAL_HTTP_HEADERS", "")
        gdal.VSICurlPartialClearCache(source)
    _authenticated_sources.clear()


def raster_layer(source, name, asset):
    options = QgsRasterLayer.LayerOptions()
    options.loadDefaultStyle = False
    layer = QgsRasterLayer(source, name, "gdal", options)
    if not layer.isValid():
        raise HubError("No valid raster layer could be created.")
    # STAC's spectral order is commonly blue/green/red (Sentinel-2 ARD).
    # Preserve native values; only select the matching display channels.
    bands = asset.get("eo:bands") or asset.get("bands") or []
    channels = {b.get("common_name") or b.get("eo:common_name"): i + 1 for i, b in enumerate(bands)}
    renderer = layer.renderer()
    if hasattr(renderer, "setRedBand") and all(
        0 < channels.get(c, 0) <= layer.bandCount() for c in ("red", "green", "blue")
    ):
        renderer.setRedBand(channels["red"])
        renderer.setGreenBand(channels["green"])
        renderer.setBlueBand(channels["blue"])
        layer.setDefaultContrastEnhancement()
    return layer


def load_asset(client, url, asset, name, *, download=False, progress=None):
    """Run in a loading task. The caller transfers returned layers to the UI."""
    kind = asset_type(asset)
    if kind not in ("COG", "GeoTIFF", "NetCDF"):
        raise HubError("This asset format is not supported.")
    if kind != "NetCDF" and not download:
        try:
            supports_ranges = client.request(url, probe_range=True)
        except HubError as error:
            if error.status in (401, 403):
                raise
            raise StreamingUnavailable("The server could not serve a byte-range request.") from error
        if not supports_ranges:
            raise StreamingUnavailable("The server does not support HTTP byte-range requests.")
        source = streaming_source(client, url)
        try:
            layer = raster_layer(source, name, asset)
        except Exception as error:
            raise StreamingUnavailable("QGIS could not open this raster remotely.") from error
        layer.setCustomProperty("eodh/remote_url", url)
        layer.setCustomProperty("eodh/workspace", client.workspace)
        layer.setCustomProperty("eodh/base", client.base)
        return [layer], True

    with tempfile.NamedTemporaryFile(
        prefix="eodh-", suffix=".nc" if kind == "NetCDF" else ".tif", delete=False
    ) as output:
        path = output.name
    try:
        client.request(url, destination=path, progress=progress)
        if kind == "NetCDF":
            from eodh_qgis.layer_utils import get_netcdf_layers

            layers = get_netcdf_layers(path, name)
        else:
            layers = [raster_layer(path, name, asset)]
        if not layers or any(not layer.isValid() for layer in layers):
            raise HubError("No valid raster layers could be created.")
        return layers, False
    except Exception:
        Path(path).unlink(missing_ok=True)
        raise


def reconnect_streams(client, layers):
    """Restore in-memory headers for protected layers after reconnecting."""
    for layer in layers:
        url = layer.customProperty("eodh/remote_url", "")
        if (
            url
            and layer.customProperty("eodh/workspace", "") == client.workspace
            and layer.customProperty("eodh/base", "") == client.base
        ):
            source = streaming_source(client, url)
            if not layer.isValid():
                layer.setDataSource(source, layer.name(), "gdal")
            layer.triggerRepaint()
