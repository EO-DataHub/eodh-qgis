"""Display and preview contracts shared with the ArcGIS EODH add-in."""

import json
import math
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit

from .hub import asset_type, href


def parsed_date(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        return None


def display_date(value, fmt="%Y-%m-%d %H:%M"):
    date = parsed_date(value)
    return date.strftime(fmt) if date else value or ""


def bbox2d(value):
    if not value or len(value) < 4:
        return None
    result = [value[0], value[1], value[3], value[4]] if len(value) == 6 else list(value[:4])
    try:
        return (
            result
            if all(math.isfinite(x) for x in result) and result[0] <= result[2] and result[1] <= result[3]
            else None
        )
    except TypeError:
        return None


def overlap(item_bbox, aoi_bbox):
    item, aoi = bbox2d(item_bbox), bbox2d(aoi_bbox)
    if not item or not aoi or aoi[2] <= aoi[0] or aoi[3] <= aoi[1]:
        return None
    width = max(0, min(item[2], aoi[2]) - max(item[0], aoi[0]))
    height = max(0, min(item[3], aoi[3]) - max(item[1], aoi[1]))
    return min(100, width * height / ((aoi[2] - aoi[0]) * (aoi[3] - aoi[1])) * 100)


def metadata(item, bbox=None, licence=None):
    props = item.get("properties") or {}
    result = [display_date(props.get("datetime"))]
    for key, pattern in (("gsd", "{:.1f} m"), ("eo:cloud_cover", "{:.1f}%")):
        if isinstance(props.get(key), (float, int)):
            result.append(pattern.format(props[key]))
    percent = overlap(item.get("bbox"), bbox)
    if percent is not None:
        result.append("< 1% overlap" if 0 < percent < 1 else f"{percent:.0f}% overlap")
    if isinstance(props.get("accuracy:geometric_rmse"), (float, int)):
        result.append(f"RMSE: {props['accuracy:geometric_rmse']:.1f} m")
    if licence:
        result.append("License: " + licence)
    return [text for text in result if text]


def default_assets(collection):
    normalized = "".join(c.lower() for c in (collection or "") if c.isalnum())
    return {
        "s2ard": ["cog"],
        "sentinel2ard": ["cog"],
        "s1ard": ["data"],
        "sentinel1ard": ["data"],
        "eocischuklai": ["data"],
        "eocischukfpar": ["data"],
        "eocischuklandcover": ["data"],
        "eocischuklandclass": ["data_lccs_class"],
        "eocischukelevation": ["data"],
    }.get(normalized, [])


def thumbnail_asset(item):
    assets = item.get("assets") or {}
    return next((a for a in assets.values() if "thumbnail" in (a.get("roles") or [])), None) or next(
        (a for key in ("thumbnail", "quicklook") for k, a in assets.items() if k.lower() == key), None
    )


def file_type(asset):
    if asset_type(asset):
        return asset_type(asset)
    mime = (asset.get("type") or "").lower()
    known = {
        "image/png": "PNG",
        "image/jpeg": "JPEG",
        "application/json": "JSON",
        "application/geo+json": "GeoJSON",
        "application/geojson": "GeoJSON",
        "application/xml": "XML",
        "text/xml": "XML",
        "text/html": "HTML",
        "text/plain": "Text",
        "application/pdf": "PDF",
        "application/geopackage+sqlite3": "GPKG",
    }
    ext = Path(urlsplit(asset.get("href", "")).path).suffix.lstrip(".").lower()
    return (
        known.get(mime)
        or {"geojson": "GeoJSON", "jpg": "JPEG", "jpeg": "JPEG"}.get(ext)
        or (mime.split("/")[-1].split(";")[0].strip().upper() if mime else ext.upper() or "File")
    )


@lru_cache(maxsize=1)
def render_config():
    return json.loads((Path(__file__).parents[1] / "brand" / "render-config.json").read_text(encoding="utf-8"))


def quick_view(item, base="https://eodatahub.org.uk"):
    renders = render_config().get(item.get("collection"), {}).get("renders") or {}
    if not renders:
        return None
    render_id, render = next(iter(renders.items()))
    assets = render.get("assets") or []
    if render.get("quicklook_georeference") or not assets or any(a not in (item.get("assets") or {}) for a in assets):
        return None
    source = item["assets"][assets[0]].get("href") if render.get("variable") else href(item, "self")
    if not source:
        return None
    params = [("url", source), ("title", render.get("title") or render_id)]
    params += [("assets", asset) for asset in assets]
    params += [("bidx", str(index)) for index in render.get("bidx") or []]
    rescale = render.get("rescale") or []
    if rescale and not isinstance(rescale[0], list):
        rescale = [rescale]
    params += [("rescale", ",".join(str(x) for x in pair[:2])) for pair in rescale if len(pair) >= 2]
    for key in ("nodata", "colormap", "variable", "colormap_name", "color_formula", "expression", "reference"):
        value = render.get(key)
        if value is not None and value != "":
            params.append(
                (key, json.dumps(value, separators=(",", ":")) if isinstance(value, (dict, bool)) else str(value))
            )
    params.append(("id", render_id))
    endpoint = (
        "xarray/tiles/{z}/{x}/{y}@1x" if render.get("variable") else "core/stac/tiles/WebMercatorQuad/{z}/{x}/{y}@1x"
    )
    return base.rstrip("/") + "/titiler/" + endpoint + "?" + urlencode(params, quote_via=quote), render.get(
        "title"
    ) or render_id
