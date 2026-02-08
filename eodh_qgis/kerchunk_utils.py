"""Kerchunk reference file parsing utilities.

This module provides functions to parse kerchunk JSON reference files
and extract NetCDF variable metadata without downloading the full NetCDF file.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any

from eodh_qgis.definitions.constants import (
    CF_COORDINATE_STANDARD_NAMES,
    EPSG_ATTRIBUTE_NAMES,
    GRID_MAPPING_NAMES,
    X_COORDINATE_NAMES,
    Y_COORDINATE_NAMES,
)
from eodh_qgis.utils import compute_geotransform


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


def load_variable_from_kerchunk(
    kerchunk_data: dict,
    var_name: str,
) -> tuple | None:
    """Load variable data using kerchunk reference (no full file download).

    Uses zarr + fsspec to read only the required variable's data via
    byte-range HTTP requests to the source NetCDF file.

    Args:
        kerchunk_data: Parsed kerchunk JSON dict
        var_name: Name of the variable to load

    Returns:
        Tuple of (data_array, attributes_dict) or None if failed
    """
    import time

    from qgis.core import Qgis, QgsMessageLog

    try:
        import fsspec
        import numpy as np
        import zarr

        t0 = time.time()

        # Create a filesystem mapper from kerchunk reference
        mapper = fsspec.get_mapper(
            "reference://",
            fo=kerchunk_data,
            remote_protocol="https",
        )

        t1 = time.time()
        QgsMessageLog.logMessage(
            f"[TIMING] fsspec mapper creation: {t1 - t0:.2f}s",
            "EODH",
            level=Qgis.Info,
        )

        # Open as zarr store (lazy - doesn't load data yet)
        store: Any = zarr.open(mapper, mode="r")

        t2 = time.time()
        QgsMessageLog.logMessage(
            f"[TIMING] zarr.open: {t2 - t1:.2f}s",
            "EODH",
            level=Qgis.Info,
        )

        # Check if variable exists
        if var_name not in store:
            return None

        # Read variable data (this fetches only the needed chunks)
        var = store[var_name]
        t3 = time.time()
        QgsMessageLog.logMessage(
            f"[TIMING] access variable: {t3 - t2:.2f}s",
            "EODH",
            level=Qgis.Info,
        )

        data = np.array(var[:])

        t4 = time.time()
        QgsMessageLog.logMessage(
            f"[TIMING] read data (var[:]): {t4 - t3:.2f}s, "
            f"shape: {data.shape}, size: {data.nbytes / 1024 / 1024:.2f} MB",
            "EODH",
            level=Qgis.Info,
        )

        # Get attributes from kerchunk refs
        refs = kerchunk_data.get("refs", {})
        zattrs_key = f"{var_name}/.zattrs"
        zattrs_str = refs.get(zattrs_key, "{}")
        try:
            attrs = json.loads(zattrs_str)
        except json.JSONDecodeError:
            attrs = {}

        QgsMessageLog.logMessage(
            f"[TIMING] TOTAL load_variable_from_kerchunk: {time.time() - t0:.2f}s",
            "EODH",
            level=Qgis.Info,
        )
        return (data, attrs)

    except Exception as e:
        QgsMessageLog.logMessage(
            f"[ERROR] load_variable_from_kerchunk failed: {e}",
            "EODH",
            level=Qgis.Warning,
        )
        return None


def get_geotransform_from_kerchunk(
    kerchunk_data: dict,
) -> tuple[float, ...] | None:
    """Extract geotransform from kerchunk coordinate arrays (xc/yc).

    Reads the 1D projection coordinate arrays and computes the GDAL geotransform.

    Args:
        kerchunk_data: Parsed kerchunk JSON dict

    Returns:
        6-element geotransform tuple or None if coordinates not found
    """
    import time

    from qgis.core import Qgis, QgsMessageLog

    try:
        import fsspec
        import zarr

        t0 = time.time()

        # Create mapper
        mapper = fsspec.get_mapper(
            "reference://",
            fo=kerchunk_data,
            remote_protocol="https",
        )

        store: Any = zarr.open(mapper, mode="r")

        t1 = time.time()
        QgsMessageLog.logMessage(
            f"[TIMING] geotransform - open store: {t1 - t0:.2f}s",
            "EODH",
            level=Qgis.Info,
        )

        xc_data = None
        yc_data = None

        for name in X_COORDINATE_NAMES:
            if name in store:
                xc_data = store[name][:]
                break

        t2 = time.time()
        QgsMessageLog.logMessage(
            f"[TIMING] geotransform - read xc: {t2 - t1:.2f}s",
            "EODH",
            level=Qgis.Info,
        )

        for name in Y_COORDINATE_NAMES:
            if name in store:
                yc_data = store[name][:]
                break

        t3 = time.time()
        QgsMessageLog.logMessage(
            f"[TIMING] geotransform - read yc: {t3 - t2:.2f}s",
            "EODH",
            level=Qgis.Info,
        )

        if xc_data is None or yc_data is None:
            return None

        result = compute_geotransform(xc_data, yc_data)

        QgsMessageLog.logMessage(
            f"[TIMING] geotransform TOTAL: {time.time() - t0:.2f}s",
            "EODH",
            level=Qgis.Info,
        )
        return result

    except Exception as e:
        QgsMessageLog.logMessage(
            f"[ERROR] get_geotransform_from_kerchunk failed: {e}",
            "EODH",
            level=Qgis.Warning,
        )
        return None
