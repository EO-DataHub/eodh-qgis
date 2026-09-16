"""Service response, error and discovery regressions with no external network."""

import io
import json
from unittest.mock import MagicMock, Mock, patch
from urllib.error import HTTPError, URLError

import pytest

from eodh_qgis.api.hub import HubClient, HubError


@pytest.fixture
def client():
    return HubClient("https://hub.test", "a workspace", "private-test-token")


def make_response(data):
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.side_effect = io.BytesIO(data).read
    response.url = "https://hub.test/resolved"
    response.headers = {"Content-Length": str(len(data))}
    return response


@pytest.mark.parametrize(
    ("data", "raw", "expected"),
    [
        (b'{"id":"one"}', False, {"id": "one", "_url": "https://hub.test/resolved"}),
        (b"", False, {"_url": "https://hub.test/resolved"}),
        (b"[1,2]", False, [1, 2]),
        (b"accepted", True, b"accepted"),
    ],
)
def test_json_post_empty_and_raw_responses(client, data, raw, expected):
    with patch("eodh_qgis.api.hub.build_opener") as opener:
        response = make_response(data)
        opener.return_value.open.return_value = response
        result = client.request("/search", "POST", {"collections": ["s2"]}, raw=raw)
        assert result == expected
        req = opener.return_value.open.call_args.args[0]
        assert req.full_url == "https://hub.test/search"
        assert req.get_method() == "POST"
        assert json.loads(req.data) == {"collections": ["s2"]}
        assert req.get_header("Content-type") == "application/json"


def test_download_writes_all_chunks_and_reports_progress(client, tmp_path):
    data = b"x" * (1024 * 1024 + 23)
    with patch("eodh_qgis.api.hub.build_opener") as opener:
        opener.return_value.open.return_value = make_response(data)
        progress = Mock()
        path = tmp_path / "raster.tif"
        assert client.request("/asset", destination=path, progress=progress) == path
        assert path.read_bytes() == data
        assert [c.args for c in progress.call_args_list] == [(1024 * 1024, len(data)), (len(data), len(data))]


@pytest.mark.parametrize("code", [401, 403, 409, 503])
def test_http_errors_preserve_status_and_redact_secrets(client, code):
    with patch("eodh_qgis.api.hub.build_opener") as opener:
        opener.return_value.open.side_effect = HTTPError(
            "https://hub.test", code, "failed", {}, io.BytesIO(b"linked credential private-test-token unavailable")
        )
        with pytest.raises(HubError) as raised:
            client.request("/data")
        assert raised.value.status == code
        assert client.token not in str(raised.value)
        if code in (401, 403):
            assert "Workspace API key" in str(raised.value)
        else:
            assert "Link your provider account" in str(raised.value)
            assert "[redacted]" in str(raised.value)


@pytest.mark.parametrize("error", [URLError("offline"), TimeoutError("timed out")])
def test_connection_errors_are_actionable(client, error):
    with patch("eodh_qgis.api.hub.build_opener") as opener:
        opener.return_value.open.side_effect = error
        with pytest.raises(HubError, match="Check your connection and retry"):
            client.request("/data")


def test_validation_encodes_workspace_name(client):
    client.request = Mock(return_value={"id": "workspace"})
    assert client.validate() == {"id": "workspace"}
    client.request.assert_called_once_with("/api/catalogue/stac/catalogs/user/catalogs/a%20workspace")


def test_aggregated_collection_uses_own_parent_search(client):
    root = "https://hub.test/api/catalogue/stac/catalogs/public"
    parent = "https://hub.test/provider"
    docs = {
        root: {
            "collections": [
                {
                    "type": "Collection",
                    "id": "s2",
                    "links": [{"rel": "parent", "href": parent}, {"rel": "self", "href": "/s2"}],
                }
            ]
        },
        parent: {"title": "Provider", "links": [{"rel": "search", "href": "/provider/query"}]},
    }
    client.request = Mock(side_effect=docs.__getitem__)
    entries = client.discover("Public")
    assert len(entries) == 1
    assert entries[0]["search"] == "https://hub.test/provider/query"
    assert entries[0]["url"] == "https://hub.test/s2"
    assert entries[0]["label"] == "Provider — s2"
    with pytest.raises(ValueError, match="Choose Public or Commercial"):
        client.discover("Unknown")


def test_cloud_detection_uses_items_link_or_search(client):
    entry = {
        "url": "https://hub.test/collections/s2",
        "search": "https://hub.test/search",
        "collection": {"id": "s2", "links": [{"rel": "items", "href": "/items?existing=1"}]},
    }
    client.request = Mock(return_value={"features": [{"properties": {"eo:cloud_cover": 0}}]})
    assert client.cloud_supported(entry)
    client.request.assert_called_once_with("https://hub.test/items?existing=1&limit=5")
    entry["collection"]["links"] = []
    client.request.reset_mock()
    client.request.return_value = {"features": [{"properties": None}]}
    assert not client.cloud_supported(entry)
    client.request.assert_called_once_with("https://hub.test/search", "POST", {"collections": ["s2"], "limit": 1})


def test_workspace_paging_labels_sorting_and_cycle_protection(client):
    root = (
        "https://hub.test/api/catalogue/stac/catalogs/user/catalogs/a%20workspace/catalogs/commercial-data/collections"
    )
    items = "https://hub.test/commercial-data/catalogs/airbus/items"
    docs = {
        root: {
            "collections": [{"id": "spot", "title": "SPOT Data", "links": [{"rel": "items", "href": items}]}],
            "links": [{"rel": "next", "href": "?page=2"}],
        },
        root + "?page=2": {
            "collections": [
                {
                    "id": "planet_data",
                    "description": "Planet Data",
                    "links": [{"rel": "items", "href": "/planet/items"}],
                }
            ],
            "links": [{"rel": "next", "href": root}],
        },
        items: {
            "features": [{"id": "older", "properties": {"created": "2026-01-01"}}],
            "links": [{"rel": "next", "href": "?page=2"}],
        },
        items + "?page=2": {
            "features": [{"id": "newer", "properties": {"updated": "2026-09-01"}}],
            "links": [{"rel": "next", "href": items}],
        },
        "https://hub.test/planet/items": {"features": [{"id": "undated"}]},
    }
    client.request = Mock(side_effect=docs.__getitem__)
    records = client.records()
    assert [r["id"] for r in records] == ["newer", "older", "undated"]
    assert [r["_provider"] for r in records] == ["Airbus", "Airbus", "Planet"]
    assert [r["_collection_label"] for r in records] == ["SPOT Data", "SPOT Data", "Planet Data"]
    assert client.request.call_count == len(docs)
