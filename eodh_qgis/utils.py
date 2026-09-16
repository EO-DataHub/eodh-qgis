"""NetCDF metadata and georeferencing helpers."""

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

    Reads subdataset names and multidimensional metadata in two file opens.

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
