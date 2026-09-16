"""Regression contracts for the ArcGIS screen and preview behavior."""

from urllib.parse import parse_qs, urlsplit

from eodh_qgis.api.presentation import default_assets, file_type, metadata, overlap, quick_view, thumbnail_asset


def test_quick_view_matches_arcgis_render_contract():
    item = {
        "collection": "sentinel2_ard",
        "links": [{"rel": "self", "href": "https://eodatahub.org.uk/items/item 1"}],
        "assets": {"cog": {"href": "https://example.test/data.tif"}},
    }
    url, title = quick_view(item)
    query = parse_qs(urlsplit(url).query)
    assert "/core/stac/tiles/WebMercatorQuad/{z}/{x}/{y}@1x?" in url
    assert title == "Natural Color"
    assert query["assets"] == ["cog"]
    assert query["bidx"] == ["3", "2", "1"]
    assert query["url"] == ["https://eodatahub.org.uk/items/item 1"]
    assert "token" not in query
    item["assets"] = {}
    assert quick_view(item) is None


def test_default_selection_and_thumbnail_fallback():
    assert default_assets("Sentinel-2_ARD") == ["cog"]
    assert default_assets("sentinel-2-l2a") == []
    assert default_assets("eocis_chuk_landclass") == ["data_lccs_class"]
    assert thumbnail_asset({"assets": {"quicklook": {"href": "preview.jpg"}}}) == {"href": "preview.jpg"}
    item = {
        "assets": {"thumbnail": {"href": "fallback.png"}, "preview": {"href": "primary.jpg", "roles": ["thumbnail"]}}
    }
    assert thumbnail_asset(item)["href"] == "primary.jpg"


def test_metadata_overlap_and_file_badges():
    assert overlap([0, 0, -5, 1, 1, 10], [0, 0, 2, 2]) == 25
    assert overlap([3, 3, 4, 4], [0, 0, 2, 2]) == 0
    assert overlap(None, [0, 0, 2, 2]) is None
    item = {
        "bbox": [0, 0, 0.1, 0.1],
        "properties": {
            "datetime": "2026-09-01T12:34:00Z",
            "gsd": 10,
            "eo:cloud_cover": 4.2,
            "accuracy:geometric_rmse": 2,
        },
    }
    assert metadata(item, [0, 0, 2, 2], "proprietary") == [
        "2026-09-01 12:34",
        "10.0 m",
        "4.2%",
        "< 1% overlap",
        "RMSE: 2.0 m",
        "License: proprietary",
    ]
    assert file_type({"href": "https://example.test/data.geojson?sig=abc"}) == "GeoJSON"
    assert file_type({"href": "https://example.test/preview", "type": "image/jpeg"}) == "JPEG"
