"""Regression contracts for the ArcGIS screen and preview behavior."""

import unittest
from urllib.parse import parse_qs, urlsplit

from eodh_qgis.api.presentation import default_assets, file_type, metadata, overlap, quick_view, thumbnail_asset


class PresentationTests(unittest.TestCase):
    def test_quick_view_matches_arcgis_render_contract(self):
        item = {
            "collection": "sentinel2_ard",
            "links": [{"rel": "self", "href": "https://eodatahub.org.uk/items/item 1"}],
            "assets": {"cog": {"href": "https://example.test/data.tif"}},
        }
        url, title = quick_view(item)
        query = parse_qs(urlsplit(url).query)
        self.assertIn("/core/stac/tiles/WebMercatorQuad/{z}/{x}/{y}@1x?", url)
        self.assertEqual(title, "Natural Color")
        self.assertEqual(query["assets"], ["cog"])
        self.assertEqual(query["bidx"], ["3", "2", "1"])
        self.assertEqual(query["url"], ["https://eodatahub.org.uk/items/item 1"])
        self.assertNotIn("token", query)
        item["assets"] = {}
        self.assertIsNone(quick_view(item))

    def test_default_selection_and_thumbnail_fallback(self):
        self.assertEqual(default_assets("Sentinel-2_ARD"), ["cog"])
        self.assertEqual(default_assets("sentinel-2-l2a"), [])
        self.assertEqual(default_assets("eocis_chuk_landclass"), ["data_lccs_class"])
        self.assertEqual(thumbnail_asset({"assets": {"quicklook": {"href": "preview.jpg"}}}), {"href": "preview.jpg"})
        item = {
            "assets": {
                "thumbnail": {"href": "fallback.png"},
                "preview": {"href": "primary.jpg", "roles": ["thumbnail"]},
            }
        }
        self.assertEqual(thumbnail_asset(item)["href"], "primary.jpg")

    def test_metadata_overlap_and_file_badges(self):
        self.assertEqual(overlap([0, 0, -5, 1, 1, 10], [0, 0, 2, 2]), 25)
        self.assertEqual(overlap([3, 3, 4, 4], [0, 0, 2, 2]), 0)
        self.assertIsNone(overlap(None, [0, 0, 2, 2]))
        item = {
            "bbox": [0, 0, 0.1, 0.1],
            "properties": {
                "datetime": "2026-09-01T12:34:00Z",
                "gsd": 10,
                "eo:cloud_cover": 4.2,
                "accuracy:geometric_rmse": 2,
            },
        }
        self.assertEqual(
            metadata(item, [0, 0, 2, 2], "proprietary"),
            ["2026-09-01 12:34", "10.0 m", "4.2%", "< 1% overlap", "RMSE: 2.0 m", "License: proprietary"],
        )
        self.assertEqual(file_type({"href": "https://example.test/data.geojson?sig=abc"}), "GeoJSON")
        self.assertEqual(file_type({"href": "https://example.test/preview", "type": "image/jpeg"}), "JPEG")


if __name__ == "__main__":
    unittest.main()
