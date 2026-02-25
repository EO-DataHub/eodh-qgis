"""Utility functions for the EODH QGIS plugin."""

from __future__ import annotations

from dataclasses import dataclass

from osgeo import gdal

from eodh_qgis.definitions.constants import (
    CF_COORDINATE_STANDARD_NAMES,
    EPSG_ATTRIBUTE_NAMES,
    GRID_MAPPING_NAMES,
    X_COORDINATE_NAMES,
    Y_COORDINATE_NAMES,
)


@dataclass
class NetCDFMetadata:
    """Consolidated metadata extracted from a NetCDF file."""

    data_variables: list[tuple[str, str]]  # List of (subdataset_uri, variable_name)
    geotransform: tuple[float, ...] | None  # 6-element GDAL geotransform
    epsg: str | None  # EPSG code as string


def compute_geotransform(xc_data, yc_data) -> tuple[float, ...] | None:
    """Compute GDAL geotransform from 1D coordinate arrays.

    Args:
        xc_data: 1D array of x coordinates (pixel centers)
        yc_data: 1D array of y coordinates (pixel centers)

    Returns:
        6-element geotransform tuple or None if arrays too short
    """
    if len(xc_data) < 2 or len(yc_data) < 2:
        return None

    pixel_width = (xc_data[-1] - xc_data[0]) / (len(xc_data) - 1)
    pixel_height = (yc_data[-1] - yc_data[0]) / (len(yc_data) - 1)

    origin_x = float(xc_data[0] - pixel_width / 2)
    origin_y = float(yc_data[-1] + pixel_height / 2)
    pixel_height_gdal = -abs(float(pixel_height))

    return (origin_x, float(pixel_width), 0.0, origin_y, 0.0, pixel_height_gdal)


def get_netcdf_metadata(file_path: str) -> NetCDFMetadata:
    """Extract all metadata from a NetCDF file with minimal file opens.

    Consolidates get_netcdf_data_variables, get_netcdf_geotransform, and
    extract_epsg_from_netcdf into just 2 file opens (instead of 4).

    Args:
        file_path: Path to NetCDF file

    Returns:
        NetCDFMetadata with data_variables, geotransform, and epsg
    """
    data_variables: list[tuple[str, str]] = []
    geotransform: tuple[float, ...] | None = None
    epsg: str | None = None

    try:
        # Handle NETCDF:"path":variable format
        if file_path.startswith("NETCDF:"):
            parts = file_path.split(":")
            if len(parts) >= 3:
                file_path = ":".join(parts[1:-1]).strip('"')

        # === OPEN 1: Get SUBDATASETS metadata ===
        ds = gdal.Open(file_path)
        if not ds:
            return NetCDFMetadata(data_variables, geotransform, epsg)

        subdatasets = ds.GetMetadata("SUBDATASETS")
        subdataset_uris = []
        if subdatasets:
            for key, value in subdatasets.items():
                if key.endswith("_NAME"):
                    subdataset_uris.append(value)
        ds = None  # Close

        # === OPEN 2: Get variables, geotransform, epsg via MULTIDIM API ===
        md_ds = gdal.OpenEx(file_path, gdal.OF_MULTIDIM_RASTER)
        if not md_ds:
            return NetCDFMetadata(data_variables, geotransform, epsg)

        root = md_ds.GetRootGroup()
        if not root:
            return NetCDFMetadata(data_variables, geotransform, epsg)

        # --- Extract data variables (filter out coordinates) ---
        for uri in subdataset_uris:
            if ":" not in uri:
                continue
            var_name = uri.split(":")[-1]

            # Skip bounds variables
            if var_name.endswith("_bnds") or var_name.endswith("_bounds"):
                continue

            # Check if it's a coordinate variable
            arr = root.OpenMDArray(var_name)
            if arr and is_coordinate_variable(arr):
                continue

            data_variables.append((uri, var_name))

        # --- Extract EPSG from grid_mapping variable ---
        for gm_name in GRID_MAPPING_NAMES:
            arr = root.OpenMDArray(gm_name)
            if arr:
                for attr in arr.GetAttributes():
                    attr_name = attr.GetName().lower()
                    if attr_name in EPSG_ATTRIBUTE_NAMES:
                        epsg = str(int(attr.Read()))
                        break
                if epsg:
                    break

        # --- Extract geotransform from xc/yc coordinate arrays ---
        xc_arr = None
        yc_arr = None

        for name in X_COORDINATE_NAMES:
            arr = root.OpenMDArray(name)
            if arr and arr.GetDimensionCount() == 1:
                xc_arr = arr
                break

        for name in Y_COORDINATE_NAMES:
            arr = root.OpenMDArray(name)
            if arr and arr.GetDimensionCount() == 1:
                yc_arr = arr
                break

        if xc_arr and yc_arr:
            xc_data = xc_arr.ReadAsArray()
            yc_data = yc_arr.ReadAsArray()
            geotransform = compute_geotransform(xc_data, yc_data)

        return NetCDFMetadata(data_variables, geotransform, epsg)

    except Exception:
        return NetCDFMetadata(data_variables, geotransform, epsg)


def extract_epsg_from_netcdf(file_path: str) -> str | None:
    """Extract EPSG code from NetCDF grid_mapping variable (CF conventions).

    NetCDF files following CF conventions store CRS info in a grid_mapping
    variable (e.g., 'polar_stereographic') which may contain an 'epsg_code'
    attribute.

    Args:
        file_path: Path to NetCDF file (can include NETCDF:"path":var format
                   or /vsicurl/ prefix for remote files)

    Returns:
        EPSG code as string, or None if not found
    """
    try:
        # Handle NETCDF:"path":variable format - extract just the file path
        if file_path.startswith("NETCDF:"):
            parts = file_path.split(":")
            # Reconstruct path - everything between first ":" and last ":"
            if len(parts) >= 3:
                file_path = ":".join(parts[1:-1]).strip('"')

        # Open with multidim API to access scalar variables
        ds = gdal.OpenEx(file_path, gdal.OF_MULTIDIM_RASTER)
        if not ds:
            return None

        root = ds.GetRootGroup()
        if not root:
            return None

        for gm_name in GRID_MAPPING_NAMES:
            arr = root.OpenMDArray(gm_name)
            if arr:
                for attr in arr.GetAttributes():
                    attr_name = attr.GetName().lower()
                    if attr_name in EPSG_ATTRIBUTE_NAMES:
                        return str(int(attr.Read()))

        return None

    except Exception:
        return None


def is_coordinate_variable(arr) -> bool:
    """Check if a GDAL MDArray is a coordinate variable using CF conventions.

    Uses CF convention attributes to identify coordinate variables:
    - 0-dimensional arrays (scalar CRS/grid_mapping variables)
    - Variables with standard_name containing latitude, longitude, time, etc.
    - Variables with axis attribute (T, X, Y, Z)

    Args:
        arr: GDAL MDArray object

    Returns:
        True if this is a coordinate variable, False if it's a data variable
    """
    # 0-dimensional = scalar (CRS, grid_mapping, etc.)
    if arr.GetDimensionCount() == 0:
        return True

    for attr in arr.GetAttributes():
        attr_name = attr.GetName().lower()
        # Check standard_name attribute
        if attr_name == "standard_name":
            val = str(attr.Read()).lower()
            if any(csn in val for csn in CF_COORDINATE_STANDARD_NAMES):
                return True
        # Check axis attribute (T, X, Y, Z indicate coordinate)
        if attr_name == "axis":
            return True

    return False


def get_netcdf_data_variables(file_path: str) -> list[tuple[str, str]]:
    """Get all data (non-coordinate) subdatasets from a NetCDF file.

    Uses CF convention attributes to identify and exclude coordinate variables.
    Also excludes bounds variables (ending in _bnds or _bounds).

    Args:
        file_path: Path to NetCDF file (can include NETCDF:"path":var format
                   or /vsicurl/ prefix for remote files)

    Returns:
        List of (subdataset_uri, variable_name) tuples for data variables only
    """
    result = []

    try:
        # Handle NETCDF:"path":variable format - extract just the file path
        if file_path.startswith("NETCDF:"):
            parts = file_path.split(":")
            if len(parts) >= 3:
                file_path = ":".join(parts[1:-1]).strip('"')

        # Get subdatasets using standard GDAL API
        ds = gdal.Open(file_path)
        if not ds:
            return result

        subdatasets = ds.GetMetadata("SUBDATASETS")
        if not subdatasets:
            return result

        # Extract subdataset URIs (keys ending in _NAME)
        subdataset_uris = []
        for key, value in subdatasets.items():
            if key.endswith("_NAME"):
                subdataset_uris.append(value)

        ds = None  # Close dataset

        # Open with multidim API to check variable attributes
        md_ds = gdal.OpenEx(file_path, gdal.OF_MULTIDIM_RASTER)
        if not md_ds:
            return result

        root = md_ds.GetRootGroup()
        if not root:
            return result

        # Check each subdataset
        for uri in subdataset_uris:
            # Extract variable name from NETCDF:"path":varname format
            if ":" in uri:
                var_name = uri.split(":")[-1]
            else:
                continue

            # Skip bounds variables
            if var_name.endswith("_bnds") or var_name.endswith("_bounds"):
                continue

            # Check if it's a coordinate variable
            arr = root.OpenMDArray(var_name)
            if arr and is_coordinate_variable(arr):
                continue

            result.append((uri, var_name))

        return result

    except Exception:
        return result


def get_netcdf_geotransform(file_path: str) -> tuple[float, ...] | None:
    """Extract geotransform from NetCDF coordinate arrays (xc/yc).

    Reads the 1D projection coordinate arrays (xc, yc) and computes
    the GDAL geotransform. These arrays contain pixel center coordinates
    in the projected CRS (e.g., meters for polar stereographic).

    Args:
        file_path: Path to NetCDF file (can include NETCDF:"path":var format)

    Returns:
        6-element geotransform tuple
        (origin_x, pixel_width, 0, origin_y, 0, pixel_height),
        or None if coordinate arrays not found
    """
    try:
        # Handle NETCDF:"path":variable format - extract just the file path
        if file_path.startswith("NETCDF:"):
            parts = file_path.split(":")
            if len(parts) >= 3:
                file_path = ":".join(parts[1:-1]).strip('"')

        # Open with multidim API to read coordinate arrays
        ds = gdal.OpenEx(file_path, gdal.OF_MULTIDIM_RASTER)
        if not ds:
            return None

        root = ds.GetRootGroup()
        if not root:
            return None

        xc_arr = None
        yc_arr = None

        for name in X_COORDINATE_NAMES:
            arr = root.OpenMDArray(name)
            if arr and arr.GetDimensionCount() == 1:
                xc_arr = arr
                break

        for name in Y_COORDINATE_NAMES:
            arr = root.OpenMDArray(name)
            if arr and arr.GetDimensionCount() == 1:
                yc_arr = arr
                break

        if not xc_arr or not yc_arr:
            return None

        xc_data = xc_arr.ReadAsArray()
        yc_data = yc_arr.ReadAsArray()

        return compute_geotransform(xc_data, yc_data)

    except Exception:
        return None
