"""Integration tests for actual GDAL HTTP range reads against a local COG."""

import re
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import numpy as np
import pytest
from osgeo import gdal, osr
from qgis.core import QgsRectangle

from eodh_qgis.api.hub import HubClient, HubError
from eodh_qgis.main import EodhQgis
from eodh_qgis.raster_loader import (
    StreamingUnavailable,
    clear_stream_credentials,
    load_asset,
    raster_layer,
    streaming_source,
)


@pytest.fixture
def local_cog(tmp_path):
    requests = []
    path = str(tmp_path / "fixture.tif")
    data = gdal.GetDriverByName("MEM").Create("", 4096, 4096, 3, gdal.GDT_Byte)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(3857)
    data.SetProjection(srs.ExportToWkt())
    data.SetGeoTransform([0, 10, 0, 40960, 0, -10])
    rng = np.random.default_rng(7)
    for i in range(1, 4):
        data.GetRasterBand(i).WriteArray(rng.integers(0, 256, (4096, 4096), dtype=np.uint8))
    gdal.Translate(path, data, format="COG", creationOptions=["COMPRESS=DEFLATE", "BLOCKSIZE=256"])
    plain_path = str(tmp_path / "plain.tif")
    gdal.Translate(plain_path, data, format="GTiff")
    data = None
    length = Path(path).stat().st_size

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            raw = self.headers.get("Range")
            requests.append((self.path, raw, self.headers.get("Authorization")))
            if self.path == "/redirect.tif":
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/fixture.tif")
                self.end_headers()
                return
            if self.path not in ("/fixture.tif", "/plain.tif", "/broken.tif"):
                self.send_error(404)
                return
            current_path = plain_path if self.path == "/plain.tif" else path
            current_length = Path(current_path).stat().st_size
            match = re.fullmatch(r"bytes=(\d+)-(\d+)", raw or "")
            if not raw:
                # use_head=no performs a size probe, aborting after headers.
                self.send_response(200)
                self.send_header("Content-Length", str(current_length))
                self.end_headers()
                return
            assert match, raw
            start, end = map(int, match.groups())
            if self.path == "/broken.tif" and start >= 16384:
                self.send_error(416)
                return
            end = min(end, current_length - 1)
            self.send_response(206)
            self.send_header("Content-Length", str(end - start + 1))
            self.send_header("Content-Range", f"bytes {start}-{end}/{current_length}")
            self.end_headers()
            with open(current_path, "rb") as source:
                source.seek(start)
                self.wfile.write(source.read(end - start + 1))

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://localhost:{server.server_port}"

    class LocalClient:
        workspace = "test"
        token = "fixture-secret"

        def __init__(self):
            self.base = base

        def request(self, url, **kwargs):
            assert kwargs == {"probe_range": True}, "Unexpected full-file download"
            with urlopen(Request(url, headers={"Range": "bytes=0-0"}), timeout=5) as response:
                return response.status == 206

    client = LocalClient()
    asset = {"type": "image/tiff", "eo:bands": [{"common_name": c} for c in ("blue", "green", "red")]}
    try:
        yield SimpleNamespace(
            client=client, base=base, requests=requests, length=length, asset=asset, plain_path=plain_path
        )
    finally:
        clear_stream_credentials()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


def test_startup_preserves_gdal_extension_configuration(iface):
    plugin = EodhQgis(iface)
    original = gdal.GetConfigOption("CPL_VSIL_CURL_ALLOWED_EXTENSIONS")
    plugin.initGui()
    try:
        assert gdal.GetConfigOption("CPL_VSIL_CURL_ALLOWED_EXTENSIONS") == original
    finally:
        plugin.unload()


def test_cog_overviews_detail_authentication_and_redirects(local_cog):
    client, base, requests, length, asset = (
        local_cog.client,
        local_cog.base,
        local_cog.requests,
        local_cog.length,
        local_cog.asset,
    )
    # Only the local fixture permits plain HTTP. Production rejects it below.
    with (
        patch("eodh_qgis.raster_loader.urlsplit", lambda url: urlsplit(url)._replace(scheme="https")),
        patch("eodh_qgis.api.hub.urlsplit", lambda url: urlsplit(url)._replace(scheme="https")),
    ):
        layers, streamed = load_asset(client, base + "/fixture.tif", asset, "fixture")
        layer = layers[0]
        assert streamed
        assert layer.isValid()
        assert layer.renderer().redBand() == 3
        assert layer.renderer().blueBand() == 1
        assert "fixture-secret" not in layer.source()
        assert "fixture-secret" not in str(layer.customPropertyKeys())
        block = layer.dataProvider().block(1, layer.extent(), 128, 128)
        assert block.isValid()
        before = len(requests)
        block = layer.dataProvider().block(1, QgsRectangle(10000, 10000, 12560, 12560), 256, 256)
        assert block.isValid()
        assert len(requests) > before
        assert any(auth == "Bearer fixture-secret" for _, _, auth in requests), requests
        fetched = sum(
            int(re.search(r"-(\d+)", r).group(1)) - int(re.search(r"=(\d+)", r).group(1)) + 1
            for _, r, _ in requests
            if r
        )
        assert fetched < length / 4, (fetched, length)
        start = len(requests)
        redirected = streaming_source(client, base + "/redirect.tif")
        remote = gdal.Open(redirected)
        assert remote is not None
        assert requests[start][2] == "Bearer fixture-secret"
        assert all(auth is None for route, _, auth in requests[start:] if route == "/fixture.tif")
        remote = None
        # The metadata-only layer can be valid despite later tile failures.
        gdal.PushErrorHandler("CPLQuietErrorHandler")
        try:
            broken_source = streaming_source(client, base + "/broken.tif")
            broken_layer = raster_layer(broken_source, "broken", asset)
            assert broken_layer.isValid()
            broken_layer = None
        finally:
            gdal.PopErrorHandler()
        for route in ("/plain.tif", "/broken.tif"):
            with patch("eodh_qgis.raster_loader.raster_layer", wraps=raster_layer) as create_layer:
                try:
                    load_asset(client, base + route, asset, "fallback")
                    raise AssertionError("Must reject missing overviews or unreadable remote pixels")
                except StreamingUnavailable:
                    pass
                create_layer.assert_not_called()

            def download(url, destination, progress):
                shutil.copyfile(local_cog.plain_path, destination)
                progress(Path(destination).stat().st_size, Path(local_cog.plain_path).stat().st_size)

            progress = Mock()
            with patch.object(client, "request", side_effect=download):
                local_layers, streamed = load_asset(
                    client, base + route, asset, "fallback", download=True, progress=progress
                )
                assert not streamed
                local_layer = local_layers[0]
                assert not local_layer.source().startswith("/vsicurl")
                assert local_layer.dataProvider().block(1, local_layer.extent(), 64, 64).isValid()
                progress.assert_called_once()
                local_path = Path(local_layer.source())
                local_layers = local_layer = None
                local_path.unlink()
        clear_stream_credentials()
        assert gdal.GetPathSpecificOption(layer.source(), "GDAL_HTTP_HEADERS", "missing") == ""


def test_streaming_rejects_insecure_urls():
    client = HubClient("https://eodatahub.org.uk", "test", "secret")
    with pytest.raises(HubError, match="HTTPS"):
        streaming_source(client, "http://example.test/data.tif")


def test_no_range_support_requests_download_fallback():
    client = Mock()
    client.request.return_value = False
    with pytest.raises(StreamingUnavailable):
        load_asset(client, "https://example.test/no-range.tif", {"type": "image/tiff"}, "no ranges")
    client.request.assert_called_once()


@pytest.mark.parametrize(("status", "fallback"), [(416, True), (503, True), (401, False), (403, False)])
def test_probe_failure_preserves_authentication_errors(status, fallback):
    client = Mock()
    client.request.side_effect = HubError("Probe failed", status)
    with pytest.raises(HubError) as raised:
        load_asset(client, "https://example.test/probe.tif", {"type": "image/tiff"}, "probe failure")
    assert isinstance(raised.value, StreamingUnavailable) == fallback


def test_workspace_stream_credentials_are_scoped_and_cleared():
    workspace_client = HubClient("https://eodatahub.org.uk", "my-workspace", "workspace-secret")
    workspace_source = streaming_source(
        workspace_client, "https://my-workspace.eodatahub-workspaces.org.uk/files/a.tif"
    )
    assert (
        gdal.GetPathSpecificOption(workspace_source, "GDAL_HTTP_HEADERS", "")
        == "Authorization: Bearer workspace-secret"
    )
    other_source = streaming_source(workspace_client, "https://other.eodatahub-workspaces.org.uk/files/a.tif")
    assert not gdal.GetPathSpecificOption(other_source, "GDAL_HTTP_HEADERS", "")
    clear_stream_credentials()
    assert not gdal.GetPathSpecificOption(workspace_source, "GDAL_HTTP_HEADERS", "")
