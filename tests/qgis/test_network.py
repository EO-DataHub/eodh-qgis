"""The QGIS network stack takes over when Python's urllib cannot reach EODH."""

import re
import socket
from unittest.mock import Mock, patch
from urllib.parse import urlsplit

import pytest

from eodh_qgis.api.hub import HubClient, HubError
from eodh_qgis.api.qgis_network import QgisNetwork

BIG = bytes(range(256)) * 12_000  # About 3 MB, several read chunks.
HUGE = bytes(range(256)) * 41_000  # About 10 MB, more than the reply's read buffer.


def as_https(url):
    # Only the local fixture uses plain HTTP; production rejects it.
    return urlsplit(url)._replace(scheme="https")


@pytest.fixture
def unreachable_proxy(monkeypatch):
    """Python's urllib must use a proxy that refuses connections, as on a locked-down network."""
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "no_proxy"):
        monkeypatch.delenv(name, raising=False)
    for name in ("http_proxy", "https_proxy"):
        monkeypatch.setenv(name, "http://127.0.0.1:9")


@pytest.fixture
def server(http_server):
    routes = http_server.routes
    routes["/data"] = lambda h: h.reply(200, b'{"id": "ok"}')
    routes["/error"] = lambda h: h.reply(503, b"<h1>Maintenance until 10:00</h1>", "text/html")
    routes["/broken"] = lambda h: h.reply(200, b"partial...", "image/tiff", length=100_000)
    routes["/redirect"] = lambda h: h.reply(302, Location=f"http://localhost:{urlsplit(http_server.base).port}/data")

    def big(handler):
        if handler.headers.get("Range") == "bytes=0-0":
            handler.reply(206, BIG[:1], "image/tiff", Content_Range=f"bytes 0-0/{len(BIG)}")
        else:
            handler.reply(200, BIG, "image/tiff")

    routes["/big"] = big
    routes["/huge"] = lambda h: h.reply(200, HUGE, "image/png")
    return http_server


@pytest.fixture
def client(server, unreachable_proxy, qgis_app):
    client = HubClient(server.base, "test", "fixture-secret", fallback=QgisNetwork())
    with patch("eodh_qgis.api.hub.urlsplit", as_https):
        yield client


def test_qgis_network_serves_json_ranges_and_downloads_when_python_cannot_connect(client, server, tmp_path):
    assert client.request("/data") == {"id": "ok", "_url": server.base + "/data"}
    assert client.network == "QGIS network"
    assert client.fallback_reasons == ["Python (proxy 127.0.0.1:9): Connection refused"]
    assert server.requests[-1] == ("/data", "Bearer fixture-secret", None)
    assert client.request("/big", probe_range=True)
    progress = Mock()
    path = tmp_path / "big.tif"
    assert client.request("/big", destination=path, progress=progress) == path
    assert path.read_bytes() == BIG
    assert progress.call_args.args == (len(BIG), len(BIG))
    assert client.request("/huge", raw=True) == HUGE


def test_qgis_network_errors_are_as_specific_as_pythons(client, tmp_path):
    client.request("/data")
    with pytest.raises(HubError) as raised:
        client.request("/error")
    assert str(raised.value) == "EODH request failed (HTTP 503 for GET 127.0.0.1/error). Maintenance until 10:00"
    assert raised.value.status == 503
    with pytest.raises(HubError) as raised:
        client.request("/broken", destination=tmp_path / "broken.tif")
    assert re.fullmatch(
        r"Lost the connection to EODH during GET 127\.0\.0\.1/broken via QGIS network: .+\. "
        r"Check your connection and retry\.",
        str(raised.value),
    )


def test_qgis_network_redirects_follow_safe_redirect_rules(client, server):
    client.request("/data")
    with pytest.raises(HubError, match="Refusing an insecure redirect"):
        client.request("/redirect")
    with patch("eodh_qgis.api.qgis_network.urlsplit", as_https):
        assert client.request("/redirect")["id"] == "ok"
    # The token stays on the original host.
    assert server.requests[-2:] == [("/redirect", "Bearer fixture-secret", None), ("/data", None, None)]


def test_unreachable_on_both_networks_names_each_cause(unreachable_proxy, qgis_app):
    with socket.socket() as closed:
        closed.bind(("127.0.0.1", 0))
        port = closed.getsockname()[1]
    client = HubClient(f"http://127.0.0.1:{port}", "test", "secret", fallback=QgisNetwork())
    with patch("eodh_qgis.api.hub.urlsplit", as_https), pytest.raises(HubError) as raised:
        client.validate()
    assert re.fullmatch(
        r"Cannot reach EODH \(127\.0\.0\.1\)\. Python \(proxy 127\.0\.0\.1:9\): Connection refused; "
        r"QGIS network \(direct\): .*refused.*\. Check your connection and retry\.",
        str(raised.value),
    )
