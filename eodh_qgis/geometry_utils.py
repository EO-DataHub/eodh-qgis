"""Geometry utilities for STAC items and footprints."""

from __future__ import annotations

import json
import tempfile

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsMessageLog,
    QgsProject,
    QgsVectorLayer,
)

from eodh_qgis.definitions.constants import PLUGIN_NAME

# Threshold for detecting polar-spanning geometries (degrees longitude)
_POLAR_LON_SPAN_THRESHOLD = 350.0


def _get_geometry_lon_span(geometry: dict) -> tuple[float, float, float] | None:
    """Get longitude span and latitude bounds from a GeoJSON geometry.

    Returns:
        Tuple of (lon_span, min_lat, max_lat) or None if cannot be computed
    """
    if not geometry or "coordinates" not in geometry:
        return None

    coords = geometry.get("coordinates", [])
    if not coords:
        return None

    # Flatten coordinates (handles Polygon, MultiPolygon, etc.)
    def flatten(c):
        if isinstance(c[0], (int, float)):
            return [c]
        result = []
        for item in c:
            result.extend(flatten(item))
        return result

    try:
        flat = flatten(coords)
        if not flat:
            return None
        lons = [p[0] for p in flat]
        lats = [p[1] for p in flat]
        return (max(lons) - min(lons), min(lats), max(lats))
    except (IndexError, TypeError):
        return None


def _create_polar_cap_geometry(min_lat: float, max_lat: float) -> dict:
    """Create a GeoJSON polygon covering a polar cap region.

    Args:
        min_lat: Southern boundary latitude
        max_lat: Northern boundary latitude

    Returns:
        GeoJSON Polygon geometry dict
    """
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [-180, min_lat],
                [-180, max_lat],
                [180, max_lat],
                [180, min_lat],
                [-180, min_lat],
            ]
        ],
    }


def item_has_geometry(item) -> bool:
    """Check if a STAC item has valid geometry.

    Args:
        item: STAC item object

    Returns:
        True if item has a geometry attribute that is not None
    """
    return hasattr(item, "geometry") and item.geometry is not None


def create_footprint_layer(item, layer_name: str | None = None) -> QgsVectorLayer | None:
    """Create a vector layer from a STAC item's geometry.

    Creates a GeoJSON temp file and loads it as an OGR vector layer.
    The layer is created with EPSG:4326 CRS (STAC standard).

    Args:
        item: STAC item with geometry attribute (GeoJSON)
        layer_name: Optional layer name (defaults to "{item.id}_footprint")

    Returns:
        QgsVectorLayer if successful, None otherwise
    """
    if not item_has_geometry(item):
        return None

    if not layer_name:
        layer_name = f"{item.id}_footprint"

    # Check if this is a polar-spanning geometry (e.g., 0-360 longitude)
    # These need special handling or they collapse to a vertical line
    geometry = item.geometry
    span_info = _get_geometry_lon_span(geometry)
    if span_info and span_info[0] >= _POLAR_LON_SPAN_THRESHOLD:
        lon_span, min_lat, max_lat = span_info
        geometry = _create_polar_cap_geometry(min_lat, max_lat)
        QgsMessageLog.logMessage(
            f"Using polar cap footprint for {item.id} (lat {min_lat:.1f} to {max_lat:.1f})",
            PLUGIN_NAME,
            level=Qgis.Info,
        )

    # Create GeoJSON FeatureCollection with the geometry
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "id": item.id,
                    "collection": str(item.collection) if item.collection else None,
                    "datetime": str(item.datetime) if item.datetime else None,
                },
            }
        ],
    }

    # Write to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".geojson", delete=False) as f:
        json.dump(geojson, f)
        temp_path = f.name

    # Create vector layer
    layer = QgsVectorLayer(temp_path, layer_name, "ogr")

    if layer.isValid():
        # Set CRS to WGS84 (STAC geometries are in EPSG:4326)
        layer.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
        return layer

    QgsMessageLog.logMessage(
        f"Failed to create footprint layer for {item.id}",
        PLUGIN_NAME,
        level=Qgis.Warning,
    )
    return None


def add_footprint_to_project(item, layer_name: str | None = None, group_name: str | None = None) -> bool:
    """Add a STAC item's footprint to the current QGIS project.

    Creates a vector layer from the item's geometry and adds it to the project.

    Args:
        item: STAC item with geometry
        layer_name: Optional layer name
        group_name: Optional layer group name (not yet implemented)

    Returns:
        True if layer was added successfully, False otherwise
    """
    layer = create_footprint_layer(item, layer_name)
    if layer is None:
        return False

    QgsProject.instance().addMapLayer(layer)
    return True
