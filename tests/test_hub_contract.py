"""Pure-Python regressions for the ArcGIS-derived backend contract."""

import unittest
from urllib.request import Request

from eodh_qgis.api.hub import (
    HubClient,
    PurchaseContext,
    SafeRedirect,
    asset_type,
    coordinates,
    provider,
    record_status,
    search_body,
)


class ContractTests(unittest.TestCase):
    def test_cloud_default_and_date_validation(self):
        body = search_body("s2", "2026-01-01", "2026-02-01")
        self.assertNotIn("filter", body)
        self.assertTrue(body["datetime"].endswith("23:59:59Z"))
        self.assertEqual(
            search_body("s2", "2026-01-01", "2026-02-01", cloud=15)["filter"]["args"],
            [{"property": "properties.eo:cloud_cover"}, 15],
        )
        with self.assertRaises(ValueError):
            search_body("s2", "2026-02-01", "2026-01-01")

    def test_bbox_ring_and_invalid_coordinates(self):
        self.assertEqual(coordinates([0, 1, 2, 3]), [[[0, 1], [2, 1], [2, 3], [0, 3], [0, 1]]])
        for bbox in ([2, 1, 0, 3], [0, 1, 2, float("nan")], [0, -91, 2, 3]):
            with self.assertRaises(ValueError):
                coordinates(bbox)

    def test_optical_payload(self):
        context = PurchaseContext(
            "https://example.test/item", "Airbus Optical", (0, 1, 2, 3), "Academic", "Analytic", "United Kingdom"
        )
        quote, order = context.requests()
        self.assertEqual(set(quote), {"coordinates", "licence", "productBundle"})
        self.assertEqual(order["endUserCountry"], "United Kingdom")
        self.assertNotIn("radarOptions", order)
        self.assertNotEqual(
            context,
            PurchaseContext(
                context.item_url, context.provider, context.bbox, context.licence, context.bundle, "France"
            ),
        )

    def test_sar_bundle_conditions(self):
        for bundle, expected in (
            ("SSC", {"orbit"}),
            ("MGD", {"orbit", "resolutionVariant"}),
            ("GEC", {"orbit", "resolutionVariant", "projection"}),
            ("EEC", {"orbit", "resolutionVariant", "projection"}),
        ):
            context = PurchaseContext(
                "https://example.test/item",
                "Airbus SAR",
                licence="Single User Licence",
                bundle=bundle,
                orbit="rapid",
                resolution="RE",
                projection="Auto",
            )
            quote, order = context.requests()
            self.assertNotIn("radarOptions", quote)
            self.assertEqual(set(order["radarOptions"]), expected)

    def test_planet_omits_licence(self):
        q, o = PurchaseContext("https://example.test/item", "Planet", bundle="Visual").requests()
        self.assertEqual(q, {"productBundle": "Visual"})
        self.assertEqual(q, o)
        with self.assertRaises(ValueError):
            PurchaseContext("https://example.test/item", "Unknown").requests()

    def test_provider_and_record_aliases(self):
        item = {
            "collection": "airbus-tsx",
            "links": [
                {
                    "rel": "self",
                    "href": "https://eodatahub.org.uk/api/catalogue/stac/catalogs/commercial/catalogs/airbus/items/1",
                }
            ],
        }
        self.assertEqual(provider(item), "Airbus SAR")
        self.assertEqual(record_status({"properties": {"order_status": "DELIVERED"}}), "delivered")
        self.assertEqual(asset_type({"href": "https://example.test/asset.tif?signature=x"}), "GeoTIFF")

    def test_cross_host_redirect_strips_bearer(self):
        req = Request("https://eodatahub.org.uk/data", headers={"Authorization": "Bearer secret"})
        redirected = SafeRedirect().redirect_request(req, None, 302, "", {}, "https://provider.test/file")
        self.assertIsNone(redirected.get_header("Authorization"))

    def test_nested_discovery_cycles_relative_links_and_pagination(self):
        base = "https://eodatahub.org.uk"
        root = base + "/api/catalogue/stac/catalogs/public"
        docs = {
            root: {"id": "public", "links": [{"rel": "child", "href": root + "/catalogs/provider"}]},
            root + "/catalogs/provider": {
                "id": "provider",
                "title": "Provider",
                "links": [
                    {"rel": "self", "href": root + "/catalogs/provider"},
                    {"rel": "search", "href": root + "/catalogs/provider/search"},
                    {"rel": "collections", "href": root + "/catalogs/provider/collections"},
                    {"rel": "child", "href": root},
                ],
            },
            root + "/catalogs/provider/collections": {
                "collections": [{"type": "Collection", "id": "a"}],
                "links": [{"rel": "next", "href": "?page=2"}],
            },
            root + "/catalogs/provider/collections?page=2": {"collections": [{"type": "Collection", "id": "b"}]},
        }
        client = HubClient(base, "workspace", "secret")
        client.request = lambda url: docs[url]
        entries = client.discover("Public")
        self.assertEqual([e["label"] for e in entries], ["Provider — a", "Provider — b"])
        self.assertEqual(entries[0]["search"], root + "/catalogs/provider/search")

    def test_post_pagination_merges_body(self):
        client = HubClient("https://eodatahub.org.uk", "workspace", "secret")
        calls = []
        client.request = lambda *args: calls.append(args)
        client.page(
            {"href": "?page=2", "method": "POST", "merge": True, "body": {"token": "next"}},
            {"collections": ["a"]},
            "https://eodatahub.org.uk/search",
        )
        self.assertEqual(
            calls[0], ("https://eodatahub.org.uk/search?page=2", "POST", {"collections": ["a"], "token": "next"})
        )


if __name__ == "__main__":
    unittest.main()
