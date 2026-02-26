"""CRS extraction and application utilities for STAC items and layers."""

from __future__ import annotations

import urllib.request
import xml.etree.ElementTree as ET

from qgis.core import Qgis, QgsCoordinateReferenceSystem, QgsMessageLog, QgsRasterLayer

from eodh_qgis.asset_utils import extract_epsg_from_asset
from eodh_qgis.utils import extract_epsg_from_netcdf


def extract_epsg_from_item(item) -> str:
    """Extract EPSG code from a STAC item's properties.

    Checks multiple possible property names used by different STAC providers.
    Does NOT fetch metadata XML - that is done lazily by apply_crs_to_layer()
    only when needed.

    Args:
        item: STAC item object with 'properties' dict

    Returns:
        EPSG code as string (e.g., "4326"), or "N/A" if not found
    """
    # Try common property names for EPSG/CRS info
    for key in ["proj:epsg", "proj:code", "epsg", "crs"]:
        val = item.properties.get(key)
        if val:
            # Handle "EPSG:4326" format -> extract "4326"
            if isinstance(val, str) and ":" in val:
                return val.split(":")[-1]
            return str(val)

    return "N/A"


def extract_epsg_from_metadata_xml(item) -> str | None:
    """Extract EPSG from metadata asset XML if available.

    Parses ISO 19115 metadata XML to find referenceSystemInfo elements.

    Args:
        item: STAC item object with 'assets' dict containing optional 'metadata' asset

    Returns:
        EPSG code as string, or None if not found
    """
    QgsMessageLog.logMessage(f"[CRS] Trying metadata XML for item {item.id}", "EODH", level=Qgis.Info)

    metadata_asset = item.assets.get("metadata")
    if not metadata_asset:
        QgsMessageLog.logMessage(f"[CRS] No metadata asset found for {item.id}", "EODH", level=Qgis.Info)
        return None

    href = getattr(metadata_asset, "href", None)
    if not href or not href.endswith(".xml"):
        QgsMessageLog.logMessage(
            f"[CRS] Metadata asset href invalid or not XML: {href}",
            "EODH",
            level=Qgis.Info,
        )
        return None

    QgsMessageLog.logMessage(f"[CRS] Fetching metadata XML from: {href}", "EODH", level=Qgis.Info)

    try:
        with urllib.request.urlopen(href, timeout=10) as response:
            xml_content = response.read()

        root = ET.fromstring(xml_content)
        namespaces = {
            "gmd": "http://www.isotc211.org/2005/gmd",
            "gco": "http://www.isotc211.org/2005/gco",
        }

        for ref_sys in root.findall(".//gmd:referenceSystemInfo", namespaces):
            code_elem = ref_sys.find(".//gmd:RS_Identifier/gmd:code/gco:CharacterString", namespaces)
            codespace_elem = ref_sys.find(".//gmd:RS_Identifier/gmd:codeSpace/gco:CharacterString", namespaces)

            if code_elem is not None and code_elem.text:
                codespace = codespace_elem.text if codespace_elem is not None else "unknown"
                QgsMessageLog.logMessage(
                    f"[CRS] Found in XML: code={code_elem.text}, codeSpace={codespace}",
                    "EODH",
                    level=Qgis.Info,
                )
                if codespace_elem is not None and codespace_elem.text == "EPSG":
                    return code_elem.text.strip()
                if code_elem.text.isdigit():
                    return code_elem.text.strip()

        QgsMessageLog.logMessage("[CRS] No EPSG found in metadata XML", "EODH", level=Qgis.Info)
        return None
    except Exception as e:
        QgsMessageLog.logMessage(f"[CRS] Failed to parse metadata XML: {e}", "EODH", level=Qgis.Warning)
        return None


def apply_crs_to_layer(
    layer: QgsRasterLayer,
    asset,
    item_epsg: str | None,
    item=None,
) -> bool:
    """Apply CRS to layer using priority order.

    Priority order:
    1. Layer's existing CRS (if already valid)
    2. Asset-level CRS from projection extension
    3. Item-level CRS from properties
    4. Metadata XML CRS (fetched lazily — only if earlier sources fail)
    5. NetCDF grid_mapping CRS

    Args:
        layer: QGIS raster layer to apply CRS to
        asset: STAC asset object
        item_epsg: EPSG from item properties (or "N/A")
        item: STAC item object (for lazy metadata XML fetch, optional)

    Returns:
        True if CRS was successfully applied
    """
    layer_name = layer.name()

    # 0. Check if layer already has a valid CRS (e.g., from VRT with projection)
    existing_crs = layer.crs()
    if existing_crs.isValid() and existing_crs.authid():
        QgsMessageLog.logMessage(
            f"[CRS] {layer_name}: Layer already has CRS {existing_crs.authid()}",
            "EODH",
            level=Qgis.Info,
        )
        return True

    # 1. Asset-level CRS
    asset_epsg = extract_epsg_from_asset(asset)
    if asset_epsg:
        crs = QgsCoordinateReferenceSystem(f"EPSG:{asset_epsg}")
        if crs.isValid():
            layer.setCrs(crs)
            QgsMessageLog.logMessage(
                f"[CRS] {layer_name}: Applied asset CRS EPSG:{asset_epsg}",
                "EODH",
                level=Qgis.Info,
            )
            return True

    # 2. Item-level CRS
    if item_epsg and item_epsg != "N/A":
        crs = QgsCoordinateReferenceSystem(f"EPSG:{item_epsg}")
        if crs.isValid():
            layer.setCrs(crs)
            QgsMessageLog.logMessage(
                f"[CRS] {layer_name}: Applied item CRS EPSG:{item_epsg}",
                "EODH",
                level=Qgis.Info,
            )
            return True

    # 3. Metadata XML CRS (lazy fetch — only when earlier sources failed)
    if item is not None:
        metadata_epsg = extract_epsg_from_metadata_xml(item)
        if metadata_epsg:
            crs = QgsCoordinateReferenceSystem(f"EPSG:{metadata_epsg}")
            if crs.isValid():
                layer.setCrs(crs)
                QgsMessageLog.logMessage(
                    f"[CRS] {layer_name}: Applied metadata XML CRS EPSG:{metadata_epsg}",
                    "EODH",
                    level=Qgis.Info,
                )
                return True

    # 4. NetCDF grid_mapping CRS (for files with polar_stereographic, etc.)
    source = layer.source()
    if source.endswith(".nc") or "NETCDF:" in source:
        netcdf_epsg = extract_epsg_from_netcdf(source)
        if netcdf_epsg:
            crs = QgsCoordinateReferenceSystem(f"EPSG:{netcdf_epsg}")
            if crs.isValid():
                layer.setCrs(crs)
                QgsMessageLog.logMessage(
                    f"[CRS] {layer_name}: Applied NetCDF grid_mapping CRS EPSG:{netcdf_epsg}",
                    "EODH",
                    level=Qgis.Info,
                )
                return True
        else:
            QgsMessageLog.logMessage(
                f"[CRS] {layer_name}: No NetCDF grid_mapping CRS found",
                "EODH",
                level=Qgis.Warning,
            )

    QgsMessageLog.logMessage(f"[CRS] {layer_name}: No CRS found", "EODH", level=Qgis.Info)
    return False
