"""Real GDAL/QGIS range reads against a local COG, with no external service."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import re
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import numpy as np
from osgeo import gdal, osr
from qgis.core import Qgis, QgsApplication, QgsRectangle
from qgis.PyQt.QtWidgets import QMainWindow

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eodh_qgis.api.hub import HubError
from eodh_qgis.main import EodhQgis
from eodh_qgis.raster_loader import StreamingUnavailable, clear_stream_credentials, load_asset, streaming_source

app = QgsApplication([], False)
app.initQgis()
# Exercise actual plugin startup: legacy process-wide extension filters broke
# encoded vsicurl URLs even when the loader passed standalone tests.
window = QMainWindow()
iface = Mock()
iface.mainWindow.return_value = window
plugin = EodhQgis(iface)
original_filter = gdal.GetConfigOption("CPL_VSIL_CURL_ALLOWED_EXTENSIONS")
plugin.initGui()
assert gdal.GetConfigOption("CPL_VSIL_CURL_ALLOWED_EXTENSIONS") == original_filter
gdal.UseExceptions()
requests = []

with tempfile.TemporaryDirectory() as directory:
    path = str(Path(directory) / "fixture.tif")
    data = gdal.GetDriverByName("MEM").Create("", 4096, 4096, 3, gdal.GDT_Byte)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(3857)
    data.SetProjection(srs.ExportToWkt())
    data.SetGeoTransform([0, 10, 0, 40960, 0, -10])
    rng = np.random.default_rng(7)
    for i in range(1, 4):
        data.GetRasterBand(i).WriteArray(rng.integers(0, 256, (4096, 4096), dtype=np.uint8))
    cog = gdal.Translate(path, data, format="COG", creationOptions=["COMPRESS=DEFLATE", "BLOCKSIZE=256"])
    cog = data = None
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
            if self.path != "/fixture.tif":
                self.send_error(404)
                return
            match = re.fullmatch(r"bytes=(\d+)-(\d+)", raw or "")
            if not raw:
                # use_head=no performs a size probe, aborting after headers.
                self.send_response(200)
                self.send_header("Content-Length", str(length))
                self.end_headers()
                return
            assert match, raw
            start, end = map(int, match.groups())
            end = min(end, length - 1)
            self.send_response(206)
            self.send_header("Content-Length", str(end - start + 1))
            self.send_header("Content-Range", f"bytes {start}-{end}/{length}")
            self.end_headers()
            with open(path, "rb") as source:
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
    # Only the local fixture permits plain HTTP. Production rejects it below.
    with patch("eodh_qgis.raster_loader.urlsplit", lambda url: urlsplit(url)._replace(scheme="https")):
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
        clear_stream_credentials()
        assert gdal.GetPathSpecificOption(layer.source(), "GDAL_HTTP_HEADERS", "missing") == ""
    try:
        streaming_source(client, base + "/fixture.tif")
        raise AssertionError("HTTP must not be accepted outside the local test")
    except HubError:
        pass
    with patch.object(client, "request", return_value=False) as request:
        try:
            load_asset(client, "https://example.test/no-range.tif", asset, "no ranges")
            raise AssertionError("Must signal that the loading task should use its download fallback")
        except StreamingUnavailable:
            pass
        assert request.call_count == 1
    for status in (416, 503, 401, 403):
        with patch.object(client, "request", side_effect=HubError("Probe failed", status)):
            try:
                load_asset(client, "https://example.test/probe.tif", asset, "probe failure")
                raise AssertionError("Probe failure must be reported")
            except HubError as error:
                fallback = isinstance(error, StreamingUnavailable)
            assert fallback == (status not in (401, 403))
    server.shutdown()
    server.server_close()
    thread.join()
    layer = layers = block = None

print(
    "PASS",
    Qgis.QGIS_VERSION,
    "COG overview/detail range reads",
    fetched,
    "of",
    length,
    "bytes; scoped auth, redirects, fallback",
)
sys.stdout.flush()
os._exit(0)
