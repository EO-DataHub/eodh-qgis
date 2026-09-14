"""Link-driven EODH transport and commercial contract shared by the dock UI.

The contract follows eodh-arcgis Services/StacClient, WorkspaceService and
Tools/CommercialHelper. This module deliberately has no Qt dependency.
"""

from __future__ import annotations

import json
import math
from collections import deque
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ENVIRONMENTS = {
    name: f"https://{prefix}eodatahub.org.uk"
    for name, prefix in (("Production", ""), ("Staging", "staging."), ("Test", "test."))
}
OPTICAL_BUNDLES = ("Visual", "General Use", "Basic", "Analytic")
OPTICAL_LICENCES = (
    "Standard",
    "Background Layer",
    "Standard + Background Layer",
    "Academic",
    "Media Licence",
    "Standard Multi End-Users (2-5)",
    "Standard Multi End-Users (6-10)",
    "Standard Multi End-Users (11-30)",
    "Standard Multi End-Users (>30)",
)
SAR_LICENCES = ("Single User Licence", "Multi User (2 - 5) Licence", "Multi User (6 - 30) Licence")
COMPLETED = {"completed", "complete", "succeeded", "fulfilled", "delivered", "available"}


class HubError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def link(document, rel):
    return next((x for x in document.get("links", []) if x.get("rel") == rel), None)


def href(document, rel, base=""):
    entry = link(document, rel)
    return urljoin(base, entry["href"]) if entry else None


def provider(item):
    path = urlsplit(href(item, "self") or "").path.lower()
    marker = "/catalogs/commercial/catalogs/"
    if marker not in path:
        return "Unknown"
    name = path.split(marker, 1)[1].split("/")[0]
    if name == "airbus":
        return (
            "Airbus SAR"
            if any(x in item.get("collection", "").lower() for x in ("sar", "tsx", "terrasar"))
            else "Airbus Optical"
        )
    return {
        "planet": "Planet",
        "opencosmos": "Open Cosmos",
        "open-cosmos": "Open Cosmos",
        "open_cosmos": "Open Cosmos",
    }.get(name, "Unknown")


def validate_bbox(bbox):
    if len(bbox) != 4 or not all(math.isfinite(x) for x in bbox):
        raise ValueError("Enter four finite WGS84 coordinates: west, south, east, north.")
    w, s, e, n = bbox
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise ValueError("AOI must have west < east and south < north, within WGS84 bounds.")
    return list(bbox)


def coordinates(bbox):
    if bbox is None:
        return None
    w, s, e, n = validate_bbox(bbox)
    return [[[w, s], [e, s], [e, n], [w, n], [w, s]]]


def search_body(collection, start, end, bbox=None, cloud=100, limit=50):
    if start > end:
        raise ValueError("The start date must be on or before the end date.")
    body = {"collections": [collection], "limit": limit, "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z"}
    if bbox is not None:
        body["bbox"] = validate_bbox(bbox)
    if cloud < 100:
        body.update(
            {
                "filter-lang": "cql2-json",
                "filter": {"op": "<=", "args": [{"property": "properties.eo:cloud_cover"}, cloud]},
            }
        )
    return body


@dataclass(frozen=True)
class PurchaseContext:
    item_url: str
    provider: str
    bbox: tuple | None = None
    licence: str = ""
    bundle: str = ""
    country: str = ""
    orbit: str = ""
    resolution: str = ""
    projection: str = ""

    def requests(self):
        p = self.provider
        if p not in {"Airbus Optical", "Airbus SAR", "Planet", "Open Cosmos"}:
            raise ValueError("This commercial provider is not supported.")
        bundles = ("SSC", "MGD", "GEC", "EEC") if p == "Airbus SAR" else OPTICAL_BUNDLES
        if p != "Open Cosmos" and self.bundle not in bundles:
            raise ValueError("Select a product bundle.")
        licences = SAR_LICENCES if p == "Airbus SAR" else OPTICAL_LICENCES
        if p.startswith("Airbus") and self.licence not in licences:
            raise ValueError("Select a licence.")
        if p == "Airbus Optical" and not self.country.strip():
            raise ValueError("Enter the end-user country.")
        data = {}
        if self.bbox is not None:
            data["coordinates"] = coordinates(self.bbox)
        if p.startswith("Airbus"):
            data["licence"] = self.licence
        if p != "Open Cosmos":
            data["productBundle"] = self.bundle
        order = dict(data)
        if p == "Airbus Optical":
            order["endUserCountry"] = self.country.strip()
        if p == "Airbus SAR":
            if self.orbit not in ("rapid", "science"):
                raise ValueError("Select a radar orbit.")
            radar = {"orbit": self.orbit}
            if self.bundle != "SSC":
                if self.resolution not in ("RE", "SE"):
                    raise ValueError("Select a radar resolution.")
                radar["resolutionVariant"] = self.resolution
            if self.bundle not in ("SSC", "MGD"):
                if self.projection not in ("Auto", "UTM", "UPS"):
                    raise ValueError("Select a radar projection.")
                radar["projection"] = self.projection
            order["radarOptions"] = radar
        return data, order


def asset_type(asset):
    mime = (asset.get("type") or "").lower()
    path = urlsplit(asset.get("href", "")).path.lower()
    if "netcdf" in mime or path.endswith(".nc"):
        return "NetCDF"
    if "tiff" in mime or path.endswith((".tif", ".tiff")):
        return "COG" if "cloud-optimized" in mime else "GeoTIFF"
    return None


def property_value(item, *keys, default="—"):
    props = item.get("properties") or {}
    return next((str(props[k]) for k in keys if props.get(k) is not None and str(props[k]).strip()), default)


def record_status(item):
    return property_value(item, "order:status", "order_status", "order:state", "status", default="unknown").lower()


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        result = super().redirect_request(req, fp, code, msg, headers, newurl)
        if result and urlsplit(req.full_url).netloc != urlsplit(newurl).netloc:
            result.remove_header("Authorization")
        if urlsplit(newurl).scheme != "https":
            raise HubError("Refusing an insecure redirect.")
        return result


class HubClient:
    def __init__(self, base, workspace, token):
        self.base, self.workspace, self.token = base, workspace, token

    def request(self, url, method="GET", body=None, raw=False, destination=None, progress=None):
        url = urljoin(self.base, url)
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.username or parsed.password:
            raise HubError("EODH links must use HTTPS without embedded credentials.")
        headers = {"Accept": "application/json"}
        if parsed.netloc == urlsplit(self.base).netloc:
            headers["Authorization"] = "Bearer " + self.token
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = Request(
            url, data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method
        )
        try:
            with build_opener(SafeRedirect()).open(req, timeout=45) as response:
                if destination is not None:
                    total = int(response.headers.get("Content-Length", 0))
                    downloaded = 0
                    with open(destination, "wb") as output:
                        while chunk := response.read(1024 * 1024):
                            output.write(chunk)
                            downloaded += len(chunk)
                            if progress:
                                progress(downloaded, total)
                    return destination
                data = response.read()
                if raw:
                    return data
                result = json.loads(data) if data else {}
                if isinstance(result, dict):
                    result.setdefault("_url", response.url)
                return result
        except HTTPError as error:
            if error.code in (401, 403):
                raise HubError(
                    "Access denied. Check the workspace name and use a current Workspace API key (not the Token ID).",
                    error.code,
                ) from None
            detail = error.read(4096).decode("utf-8", errors="replace").replace(self.token, "[redacted]")
            if "credential" in detail.lower() or "linked" in detail.lower():
                detail = "Link your provider account in EODH Workspace settings. " + detail
            raise HubError(f"EODH request failed ({error.code}). {detail}", error.code) from None
        except (URLError, TimeoutError) as error:
            raise HubError("Cannot reach EODH. Check your connection and retry.") from error

    def validate(self):
        return self.request(f"/api/catalogue/stac/catalogs/user/catalogs/{quote(self.workspace, safe='')}")

    def discover(self, root):
        if root not in ("Public", "Commercial"):
            raise ValueError("Choose Public or Commercial.")
        url = self.base + "/api/catalogue/stac/catalogs/" + root.lower()
        pending = deque([(url, root, url, None)])
        visited, entries = set(), {}
        while pending:
            url, label, owner, search = pending.popleft()
            canonical = url.split("#")[0].rstrip("/")
            if canonical in visited:
                continue
            visited.add(canonical)
            doc = self.request(url)
            self._discover_doc(doc, url, label, owner, search, pending, entries)
        return sorted(entries.values(), key=lambda entry: entry["label"].casefold())

    def _discover_doc(self, doc, url, label, owner, search, pending, entries):
        if "collections" in doc or "catalogs" in doc:
            for child in doc.get("collections", []) + doc.get("catalogs", []):
                self._discover_doc(child, url, label, owner, search, pending, entries)
            next_url = href(doc, "next", url)
            if next_url:
                pending.append((next_url, label, owner, search))
        elif doc.get("type") == "Collection":
            actual_owner = href(doc, "parent", url) or owner
            if actual_owner.rstrip("/") != owner.rstrip("/"):
                # Aggregated collection pages can contain collections from a
                # deeper provider; resolve that catalogue's advertised search.
                parent = self.request(actual_owner)
                label = parent.get("title") or parent.get("id") or label
                search = href(parent, "search", actual_owner) or actual_owner.rstrip("/") + "/search"
            owner = actual_owner
            ident = owner.rstrip("/") + "::" + doc["id"]
            entries[ident] = {
                "collection": doc,
                "label": label + " — " + (doc.get("title") or doc["id"]),
                "url": href(doc, "self", url) or url,
                "search": search or owner.rstrip("/") + "/search",
            }
        else:
            owner = href(doc, "self", url) or url
            label = doc.get("title") or doc.get("id") or label
            search = href(doc, "search", owner) or search
            for entry in doc.get("links", []):
                if entry.get("rel") in ("child", "catalog", "catalogs", "data", "collections", "next"):
                    pending.append((urljoin(owner, entry["href"]), label, owner, search))

    def cloud_supported(self, entry):
        url = href(entry["collection"], "items", entry["url"])
        if url:
            doc = self.request(url + ("&" if "?" in url else "?") + "limit=5")
        else:
            doc = self.request(entry["search"], "POST", {"collections": [entry["collection"]["id"]], "limit": 1})
        return any("eo:cloud_cover" in (i.get("properties") or {}) for i in doc.get("features", []))

    def page(self, entry, previous_body=None, base=None):
        body = entry.get("body")
        if entry.get("merge"):
            body = dict(previous_body or {}, **(body or {}))
        return self.request(urljoin(base or self.base, entry["href"]), entry.get("method", "GET"), body)

    def records(self):
        url = (
            self.base
            + f"/api/catalogue/stac/catalogs/user/catalogs/{quote(self.workspace, safe='')}/catalogs/commercial-data/collections"
        )
        records, visited = [], set()
        while url and url not in visited:
            visited.add(url)
            page = self.request(url)
            for collection in page.get("collections", []):
                items_url = href(collection, "items", url)
                label = collection["id"].replace("_", "-").split("-")[0].title()
                if items_url and "/commercial-data/catalogs/" in items_url:
                    label = items_url.split("/commercial-data/catalogs/", 1)[1].split("/")[0].title()
                seen = set()
                while items_url and items_url not in seen:
                    seen.add(items_url)
                    items = self.request(items_url)
                    for item in items.get("features", []):
                        item["_provider"] = label
                        item["_collection_label"] = (
                            collection.get("title") or collection.get("description") or collection["id"]
                        )
                        records.append(item)
                    items_url = href(items, "next", items_url)
            url = href(page, "next", url)
        return sorted(
            records, key=lambda i: property_value(i, "updated", "created", "order:date", default=""), reverse=True
        )
