"""Kerchunk reference file parsing utilities.

This module provides functions to parse kerchunk JSON reference files
and extract NetCDF variable metadata without downloading the full NetCDF file.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass

from eodh_qgis.definitions.constants import (
    CF_COORDINATE_STANDARD_NAMES,
    EPSG_ATTRIBUTE_NAMES,
    GRID_MAPPING_NAMES,
)


@dataclass
class NetCDFVariableInfo:
    """Information about a NetCDF variable extracted from kerchunk."""

    name: str
    long_name: str | None
    standard_name: str | None
    units: str | None
    shape: tuple[int, ...]
    dimensions: list[str]


def is_kerchunk_file(data: dict) -> bool:
    """Check if a dictionary represents a valid kerchunk file.

    Args:
        data: Parsed JSON dictionary

    Returns:
        True if this is a kerchunk file, False otherwise
    """
    return isinstance(data, dict) and "refs" in data


def parse_kerchunk_json(json_path: str) -> dict | None:
    """Load and parse a kerchunk reference JSON file.

    Args:
        json_path: Path or URL to kerchunk JSON file

    Returns:
        Parsed JSON dict, or None if failed
    """
    try:
        if json_path.startswith(("http://", "https://")):
            with urllib.request.urlopen(json_path, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        else:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)

        if is_kerchunk_file(data):
            return data
        return None
    except Exception:
        return None


def _is_coordinate_variable_kerchunk(zattrs: dict, zarray: dict) -> bool:
    """Check if variable is a coordinate variable based on kerchunk metadata.

    Uses CF conventions to identify coordinate variables:
    - 0-dimensional arrays (scalar CRS/grid_mapping variables)
    - Variables with standard_name containing latitude, longitude, time, etc.
    - Variables with axis attribute (T, X, Y, Z)

    Args:
        zattrs: Parsed .zattrs dictionary for the variable
        zarray: Parsed .zarray dictionary for the variable

    Returns:
        True if coordinate variable, False if data variable
    """
    # Check for scalar (0-dimensional) - e.g., grid_mapping variables
    shape = zarray.get("shape", [])
    if not shape:
        return True

    # Check standard_name for coordinate identifiers
    standard_name = zattrs.get("standard_name", "").lower()
    if any(csn in standard_name for csn in CF_COORDINATE_STANDARD_NAMES):
        return True

    # Check axis attribute (T, X, Y, Z indicate coordinate)
    if "axis" in zattrs:
        return True

    return False


def extract_variables_from_kerchunk(
    kerchunk_data: dict,
) -> list[NetCDFVariableInfo]:
    """Extract variable information from parsed kerchunk data.

    Uses CF conventions to identify and exclude coordinate variables.
    Also excludes bounds variables (ending in _bnds or _bounds).

    Args:
        kerchunk_data: Parsed kerchunk JSON dict

    Returns:
        List of NetCDFVariableInfo for data variables only
    """
    refs = kerchunk_data.get("refs", {})
    variables: list[NetCDFVariableInfo] = []

    # Find all unique variable names by looking for .zarray keys
    var_names: set[str] = set()
    for key in refs:
        if key.endswith("/.zarray"):
            var_name = key[: -len("/.zarray")]
            var_names.add(var_name)

    for var_name in sorted(var_names):
        # Skip bounds variables
        if var_name.endswith("_bnds") or var_name.endswith("_bounds"):
            continue

        # Get array metadata
        zarray_key = f"{var_name}/.zarray"
        zattrs_key = f"{var_name}/.zattrs"

        zarray_str = refs.get(zarray_key, "{}")
        zattrs_str = refs.get(zattrs_key, "{}")

        try:
            zarray = json.loads(zarray_str)
            zattrs = json.loads(zattrs_str)
        except json.JSONDecodeError:
            continue

        # Skip coordinate variables
        if _is_coordinate_variable_kerchunk(zattrs, zarray):
            continue

        # Extract variable info
        shape = tuple(zarray.get("shape", []))
        dimensions = zattrs.get("_ARRAY_DIMENSIONS", [])
        long_name = zattrs.get("long_name")
        standard_name = zattrs.get("standard_name")
        units = zattrs.get("units")

        variables.append(
            NetCDFVariableInfo(
                name=var_name,
                long_name=long_name,
                standard_name=standard_name,
                units=units,
                shape=shape,
                dimensions=dimensions,
            )
        )

    return variables


def extract_epsg_from_kerchunk(kerchunk_data: dict) -> str | None:
    """Extract EPSG code from kerchunk grid_mapping variable.

    Looks for grid_mapping variables (polar_stereographic, crs, etc.) and
    extracts the epsg_code attribute from their .zattrs.

    Args:
        kerchunk_data: Parsed kerchunk JSON dict

    Returns:
        EPSG code as string, or None if not found
    """
    refs = kerchunk_data.get("refs", {})

    for gm_name in GRID_MAPPING_NAMES:
        zattrs_key = f"{gm_name}/.zattrs"
        zattrs_str = refs.get(zattrs_key)

        if not zattrs_str:
            continue

        try:
            zattrs = json.loads(zattrs_str)
            for attr_name in EPSG_ATTRIBUTE_NAMES:
                if attr_name in zattrs:
                    return str(zattrs[attr_name])
        except json.JSONDecodeError:
            continue

    return None


def get_variable_display_info(var_info: NetCDFVariableInfo) -> str:
    """Format variable info for display in selection dialog.

    Args:
        var_info: Variable information

    Returns:
        Formatted string like
        "sea_ice_thickness - Sea ice thickness (m) [1, 2240, 1520]"
    """
    parts = [var_info.name]

    # Add long_name if available
    if var_info.long_name:
        parts.append(f"- {var_info.long_name}")

    # Add units if available
    if var_info.units:
        parts.append(f"({var_info.units})")

    # Add shape
    shape_str = ", ".join(str(d) for d in var_info.shape)
    parts.append(f"[{shape_str}]")

    return " ".join(parts)
