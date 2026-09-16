"""Service response, error and discovery regressions with no external network."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from urllib.error import HTTPError, URLError

from eodh_qgis.api.hub import HubClient, HubError


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.client = HubClient("https://hub.test", "a workspace", "private-test-token")

    def response(self, data):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.side_effect = io.BytesIO(data).read
        response.url = "https://hub.test/resolved"
        response.headers = {"Content-Length": str(len(data))}
        return response

    def test_json_post_empty_and_raw_responses(self):
        for data, raw, expected in (
            (b'{"id":"one"}', False, {"id": "one", "_url": "https://hub.test/resolved"}),
            (b"", False, {"_url": "https://hub.test/resolved"}),
            (b"[1,2]", False, [1, 2]),
            (b"accepted", True, b"accepted"),
        ):
            with self.subTest(data=data), patch("eodh_qgis.api.hub.build_opener") as opener:
                response = self.response(data)
                opener.return_value.open.return_value = response
                result = self.client.request("/search", "POST", {"collections": ["s2"]}, raw=raw)
                self.assertEqual(result, expected)
                req = opener.return_value.open.call_args.args[0]
                self.assertEqual(req.full_url, "https://hub.test/search")
                self.assertEqual(req.get_method(), "POST")
                self.assertEqual(json.loads(req.data), {"collections": ["s2"]})
                self.assertEqual(req.get_header("Content-type"), "application/json")

    def test_download_writes_all_chunks_and_reports_progress(self):
        data = b"x" * (1024 * 1024 + 23)
        with tempfile.TemporaryDirectory() as directory, patch("eodh_qgis.api.hub.build_opener") as opener:
            opener.return_value.open.return_value = self.response(data)
            progress = Mock()
            path = Path(directory) / "raster.tif"
            self.assertEqual(self.client.request("/asset", destination=path, progress=progress), path)
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(
                [c.args for c in progress.call_args_list], [(1024 * 1024, len(data)), (len(data), len(data))]
            )

    def test_http_errors_preserve_status_and_redact_secrets(self):
        for code in (401, 403, 409, 503):
            with self.subTest(code=code), patch("eodh_qgis.api.hub.build_opener") as opener:
                opener.return_value.open.side_effect = HTTPError(
                    "https://hub.test",
                    code,
                    "failed",
                    {},
                    io.BytesIO(b"linked credential private-test-token unavailable"),
                )
                with self.assertRaises(HubError) as raised:
                    self.client.request("/data")
                self.assertEqual(raised.exception.status, code)
                self.assertNotIn(self.client.token, str(raised.exception))
                if code in (401, 403):
                    self.assertIn("Workspace API key", str(raised.exception))
                else:
                    self.assertIn("Link your provider account", str(raised.exception))
                    self.assertIn("[redacted]", str(raised.exception))

    def test_connection_errors_are_actionable(self):
        for error in (URLError("offline"), TimeoutError("timed out")):
            with self.subTest(error=error), patch("eodh_qgis.api.hub.build_opener") as opener:
                opener.return_value.open.side_effect = error
                with self.assertRaisesRegex(HubError, "Check your connection and retry"):
                    self.client.request("/data")

    def test_validation_encodes_workspace_name(self):
        self.client.request = Mock(return_value={"id": "workspace"})
        self.assertEqual(self.client.validate(), {"id": "workspace"})
        self.client.request.assert_called_once_with("/api/catalogue/stac/catalogs/user/catalogs/a%20workspace")

    def test_aggregated_collection_uses_own_parent_search(self):
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
        self.client.request = Mock(side_effect=docs.__getitem__)
        entries = self.client.discover("Public")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["search"], "https://hub.test/provider/query")
        self.assertEqual(entries[0]["url"], "https://hub.test/s2")
        self.assertEqual(entries[0]["label"], "Provider — s2")
        with self.assertRaises(ValueError):
            self.client.discover("Unknown")

    def test_cloud_detection_uses_items_link_or_search(self):
        entry = {
            "url": "https://hub.test/collections/s2",
            "search": "https://hub.test/search",
            "collection": {"id": "s2", "links": [{"rel": "items", "href": "/items?existing=1"}]},
        }
        self.client.request = Mock(return_value={"features": [{"properties": {"eo:cloud_cover": 0}}]})
        self.assertTrue(self.client.cloud_supported(entry))
        self.client.request.assert_called_once_with("https://hub.test/items?existing=1&limit=5")
        entry["collection"]["links"] = []
        self.client.request.reset_mock()
        self.client.request.return_value = {"features": [{"properties": None}]}
        self.assertFalse(self.client.cloud_supported(entry))
        self.client.request.assert_called_once_with(
            "https://hub.test/search", "POST", {"collections": ["s2"], "limit": 1}
        )

    def test_workspace_paging_labels_sorting_and_cycle_protection(self):
        root = "https://hub.test/api/catalogue/stac/catalogs/user/catalogs/a%20workspace/catalogs/commercial-data/collections"
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
        self.client.request = Mock(side_effect=docs.__getitem__)
        records = self.client.records()
        self.assertEqual([r["id"] for r in records], ["newer", "older", "undated"])
        self.assertEqual([r["_provider"] for r in records], ["Airbus", "Airbus", "Planet"])
        self.assertEqual([r["_collection_label"] for r in records], ["SPOT Data", "SPOT Data", "Planet Data"])
        self.assertEqual(self.client.request.call_count, len(docs))
