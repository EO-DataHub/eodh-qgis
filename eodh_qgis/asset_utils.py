"""Asset detection and formatting utilities for STAC items."""

from __future__ import annotations

from eodh_qgis.definitions.asset_types import AssetRole
from eodh_qgis.definitions.constants import (
    DATA_ASSET_KEYS,
    LOADABLE_EXTENSIONS,
    LOADABLE_MIME_TYPES,
)
from eodh_qgis.kerchunk_utils import is_kerchunk_file, parse_kerchunk_json


def format_bbox(bbox: list | tuple | None) -> str:
    """Format bounding box as a readable string with direction labels.

    Args:
        bbox: Bounding box as [West, South, East, North] or None

    Returns:
        Formatted string like "W: -180.00, S: -90.00, E: 180.00, N: 90.00"
        or "N/A" if bbox is invalid
    """
    if bbox and len(bbox) == 4:
        west, south, east, north = bbox
        return f"W: {west:.2f}, S: {south:.2f}, E: {east:.2f}, N: {north:.2f}"
    return "N/A"


def get_asset_file_type(asset) -> str:
    """Determine the file type of an asset from MIME type or extension.

    Args:
        asset: STAC asset object with optional 'type' and 'href' attributes

    Returns:
        File type string (e.g., "GeoTIFF", "COG", "NetCDF", "PNG")
        Never returns empty string - returns "Unknown" as fallback
    """
    asset_type = getattr(asset, "type", None)
    href = getattr(asset, "href", "")

    # Check MIME type first
    if asset_type:
        if "geotiff" in asset_type.lower() or asset_type == "image/tiff":
            if "cloud-optimized" in asset_type.lower():
                return "COG"
            return "GeoTIFF"
        if "netcdf" in asset_type.lower():
            return "NetCDF"
        if asset_type == "image/png":
            return "PNG"
        if asset_type in ["image/jpeg", "image/jpg"]:
            return "JPEG"
        if "xml" in asset_type.lower():
            return "XML"
        if "json" in asset_type.lower():
            return "JSON"
        if "text" in asset_type.lower():
            return "Text"

    # Fallback to file extension
    if href:
        href_lower = href.lower()
        if href_lower.endswith(".tif") or href_lower.endswith(".tiff"):
            return "GeoTIFF"
        if href_lower.endswith(".nc"):
            return "NetCDF"
        if href_lower.endswith(".png"):
            return "PNG"
        if href_lower.endswith(".jpg") or href_lower.endswith(".jpeg"):
            return "JPEG"
        if href_lower.endswith(".xml"):
            return "XML"
        if href_lower.endswith(".json"):
            return "JSON"

        # Return raw extension if unknown type
        if "." in href:
            ext = href.rsplit(".", 1)[-1].split("?")[0].upper()
            if ext:
                return f".{ext}"

    return "Unknown"


def is_loadable_asset(asset, asset_key: str | None = None) -> bool:
    """Check if an asset can be loaded as a QGIS layer.

    Args:
        asset: STAC asset object
        asset_key: Optional key name of the asset (used to skip thumbnails)

    Returns:
        True if the asset can be loaded as a raster layer
    """
    if not hasattr(asset, "href"):
        return False

    # Skip thumbnails
    roles = getattr(asset, "roles", []) or []
    if AssetRole.THUMBNAIL.value in roles or asset_key == AssetRole.THUMBNAIL.value:
        return False

    asset_type = getattr(asset, "type", None)
    # Check if asset type contains any loadable type
    if asset_type:
        for lt in LOADABLE_MIME_TYPES:
            if lt in asset_type or asset_type in lt:
                return True

    # Fallback: check file extension
    href = asset.href.lower()
    for ext in LOADABLE_EXTENSIONS:
        if href.endswith(ext):
            return True

    # If type is None but it's a known data asset, try it anyway
    if asset_type is None and asset_key in DATA_ASSET_KEYS:
        return True

    return False


def get_all_loadable_assets(item) -> list[tuple[str, object]]:
    """Find all loadable assets from a STAC item.

    Args:
        item: STAC item object with 'assets' dict

    Returns:
        List of (asset_key, asset) tuples for loadable assets
    """
    loadable = []
    for asset_key, asset in item.assets.items():
        if is_loadable_asset(asset, asset_key):
            loadable.append((asset_key, asset))
    return loadable


def extract_epsg_from_asset(asset) -> str | None:
    """Extract EPSG code from an individual asset.

    Checks pystac projection extension and common extra_fields keys.

    Args:
        asset: STAC asset object

    Returns:
        EPSG code as string (e.g., "4326"), or None if not found
    """
    # Try pystac projection extension
    try:
        if hasattr(asset, "ext") and hasattr(asset.ext, "proj"):
            proj = asset.ext.proj
            if proj.epsg:
                return str(proj.epsg)
            if proj.code:
                code = proj.code
                return code.split(":")[-1] if ":" in code else code
    except Exception:
        pass

    # Check asset extra_fields for projection info
    if hasattr(asset, "extra_fields"):
        for key in ["proj:epsg", "proj:code", "epsg", "crs"]:
            if key in asset.extra_fields:
                val = asset.extra_fields.get(key)
                if val:
                    if isinstance(val, str) and ":" in val:
                        return val.split(":")[-1]
                    return str(val)

    return None


def format_assets_with_crs(item) -> str:
    """Format asset keys with their file type and CRS info.

    Args:
        item: STAC item object with 'assets' dict

    Returns:
        Comma-separated string of "key (type, epsg)" entries,
        or "N/A" if no assets
    """
    if not item.assets:
        return "N/A"

    parts = []
    for key, asset in item.assets.items():
        file_type = get_asset_file_type(asset)
        epsg = extract_epsg_from_asset(asset)

        info_parts = [file_type]
        if epsg:
            info_parts.append(epsg)

        parts.append(f"{key} ({', '.join(info_parts)})")

    return ", ".join(parts)


def find_kerchunk_reference(item) -> tuple[str, dict] | None:
    """Find and parse a kerchunk reference file from a STAC item.

    Searches all JSON assets in the item and checks if any is a valid
    kerchunk file (has "refs" key).

    Args:
        item: STAC item object with 'assets' dict

    Returns:
        Tuple of (href, parsed_data) for the first valid kerchunk file found,
        or None if no kerchunk file exists
    """
    if not item.assets:
        return None

    for asset_key, asset in item.assets.items():
        href = getattr(asset, "href", "")
        asset_type = getattr(asset, "type", "") or ""

        # Check if this is a JSON asset
        is_json = href.lower().endswith(".json") or "json" in asset_type.lower()

        if not is_json:
            continue

        # Try to parse and check if it's a kerchunk file
        kerchunk_data = parse_kerchunk_json(href)
        if kerchunk_data and is_kerchunk_file(kerchunk_data):
            return (href, kerchunk_data)

    return None
