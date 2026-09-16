"""Pure-Python regressions for the ArcGIS-derived backend contract."""

from unittest.mock import MagicMock, patch
from urllib.request import Request

import pytest

from eodh_qgis.api.hub import (
    HubClient,
    PurchaseContext,
    SafeRedirect,
    asset_type,
    coordinates,
    provider,
    record_status,
    requires_auth,
    search_body,
)


@pytest.mark.parametrize(
    ("status", "content_range", "expected"), [(206, "bytes 0-0/2000000000", True), (200, "", False)]
)
def test_range_probe_never_consumes_full_response(status, content_range, expected):
    client = HubClient("https://hub.test", "workspace", "secret")
    response = MagicMock()
    response.status = status
    response.headers = {"Content-Range": content_range}
    response.__enter__.return_value = response
    with patch("eodh_qgis.api.hub.build_opener") as opener:
        opener.return_value.open.return_value = response
        assert client.request("https://hub.test/data.tif", probe_range=True) == expected
        request = opener.return_value.open.call_args.args[0]
        assert request.get_header("Range") == "bytes=0-0"
        assert request.get_header("Authorization") == "Bearer secret"
        response.read.assert_not_called()
        response.__exit__.assert_called_once()


def test_workspace_asset_authentication():
    client = HubClient("https://eodatahub.org.uk", "samples-airbus-optical", "secret")
    workspace = "https://samples-airbus-optical.eodatahub-workspaces.org.uk/files/data.tif"
    for url, authorized in (
        (workspace, True),
        (workspace.replace(".org.uk/", ".org.uk:443/"), True),
        (workspace.replace("samples-airbus-optical", "another-workspace"), False),
        (workspace.replace(".org.uk/", ".org.uk.evil.test/"), False),
        (workspace.replace(".org.uk/", ".org.uk:444/"), False),
        ("https://dap.ceda.ac.uk/public.tif", False),
    ):
        with patch("eodh_qgis.api.hub.build_opener") as opener:
            response = MagicMock(status=206)
            response.headers = {"Content-Range": "bytes 0-0/100"}
            response.__enter__.return_value = response
            opener.return_value.open.return_value = response
            client.request(url, probe_range=True)
            request = opener.return_value.open.call_args.args[0]
            assert request.get_header("Authorization") == ("Bearer secret" if authorized else None)
    assert not requires_auth(client.base, client.workspace, workspace.replace("https:", "http:"))
    assert not requires_auth("https://staging.eodatahub.org.uk", client.workspace, workspace)
    assert not requires_auth(client.base, "other.samples-airbus-optical", workspace)
    req = Request(workspace, headers={"Authorization": "Bearer secret"})
    redirected = SafeRedirect().redirect_request(req, None, 302, "", {}, "https://external.test/file")
    assert redirected.get_header("Authorization") is None


def test_cloud_default_and_date_validation():
    body = search_body("s2", "2026-01-01", "2026-02-01")
    assert "filter" not in body
    assert body["datetime"].endswith("23:59:59Z")
    assert search_body("s2", "2026-01-01", "2026-02-01", cloud=15)["filter"]["args"] == [
        {"property": "properties.eo:cloud_cover"},
        15,
    ]
    with pytest.raises(ValueError, match="start date"):
        search_body("s2", "2026-02-01", "2026-01-01")


@pytest.mark.parametrize("bbox", [[2, 1, 0, 3], [0, 1, 2, float("nan")], [0, -91, 2, 3]])
def test_bbox_ring_and_invalid_coordinates(bbox):
    assert coordinates([0, 1, 2, 3]) == [[[0, 1], [2, 1], [2, 3], [0, 3], [0, 1]]]
    with pytest.raises(ValueError, match="WGS84"):
        coordinates(bbox)


def test_optical_payload():
    context = PurchaseContext(
        "https://example.test/item", "Airbus Optical", (0, 1, 2, 3), "Academic", "Analytic", "United Kingdom"
    )
    quote, order = context.requests()
    assert set(quote) == {"coordinates", "licence", "productBundle"}
    assert order["endUserCountry"] == "United Kingdom"
    assert "radarOptions" not in order
    assert context != PurchaseContext(
        context.item_url, context.provider, context.bbox, context.licence, context.bundle, "France"
    )


@pytest.mark.parametrize(
    ("bundle", "expected"),
    [
        ("SSC", {"orbit"}),
        ("MGD", {"orbit", "resolutionVariant"}),
        ("GEC", {"orbit", "resolutionVariant", "projection"}),
        ("EEC", {"orbit", "resolutionVariant", "projection"}),
    ],
)
def test_sar_bundle_conditions(bundle, expected):
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
    assert "radarOptions" not in quote
    assert set(order["radarOptions"]) == expected


def test_planet_omits_licence():
    q, o = PurchaseContext("https://example.test/item", "Planet", bundle="Visual").requests()
    assert q == {"productBundle": "Visual"}
    assert q == o
    with pytest.raises(ValueError, match="provider is not supported"):
        PurchaseContext("https://example.test/item", "Unknown").requests()


def test_provider_and_record_aliases():
    item = {
        "collection": "airbus-tsx",
        "links": [
            {
                "rel": "self",
                "href": "https://eodatahub.org.uk/api/catalogue/stac/catalogs/commercial/catalogs/airbus/items/1",
            }
        ],
    }
    assert provider(item) == "Airbus SAR"
    assert record_status({"properties": {"order_status": "DELIVERED"}}) == "delivered"
    assert asset_type({"href": "https://example.test/asset.tif?signature=x"}) == "GeoTIFF"


def test_cross_host_redirect_strips_bearer():
    req = Request("https://eodatahub.org.uk/data", headers={"Authorization": "Bearer secret"})
    redirected = SafeRedirect().redirect_request(req, None, 302, "", {}, "https://provider.test/file")
    assert redirected.get_header("Authorization") is None


def test_nested_discovery_cycles_relative_links_and_pagination():
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
    assert [e["label"] for e in entries] == ["Provider — a", "Provider — b"]
    assert entries[0]["search"] == root + "/catalogs/provider/search"


def test_post_pagination_merges_body():
    client = HubClient("https://eodatahub.org.uk", "workspace", "secret")
    calls = []
    client.request = lambda *args: calls.append(args)
    client.page(
        {"href": "?page=2", "method": "POST", "merge": True, "body": {"token": "next"}},
        {"collections": ["a"]},
        "https://eodatahub.org.uk/search",
    )
    assert calls[0] == ("https://eodatahub.org.uk/search?page=2", "POST", {"collections": ["a"], "token": "next"})
