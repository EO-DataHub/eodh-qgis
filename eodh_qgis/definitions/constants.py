"""Plugin-wide constants for EODH QGIS."""

# Plugin metadata
PLUGIN_NAME = "EODH"

# UI constants
DEFAULT_PAGE_SIZE = 50
THUMBNAIL_SIZE = (150, 150)

# MIME types that can be loaded as QGIS layers
LOADABLE_MIME_TYPES = [
    "image/tiff; application=geotiff; profile=cloud-optimized",
    "image/tiff; application=geotiff",
    "application/x-netcdf",
    "application/netcdf",
    "image/tiff",
    "image/png",
    "image/jpeg",
]

# File extensions that can be loaded as QGIS layers
LOADABLE_EXTENSIONS = [
    ".tif",
    ".tiff",
    ".nc",
    ".png",
    ".jpg",
    ".jpeg",
]

# NetCDF-specific MIME types
NETCDF_MIME_TYPES = [
    "application/x-netcdf",
    "application/netcdf",
]

# COG/GeoTIFF MIME types (for vsicurl streaming)
COG_MIME_TYPES = [
    "image/tiff; application=geotiff; profile=cloud-optimized",
    "image/tiff; application=geotiff",
    "image/tiff",
]

# Asset keys that are typically data assets
DATA_ASSET_KEYS = ["quicklook", "data", "visual", "image"]

# CF convention standard names that indicate coordinate variables
CF_COORDINATE_STANDARD_NAMES = [
    "latitude",
    "longitude",
    "time",
    "projection_x_coordinate",
    "projection_y_coordinate",
]

# Grid mapping variable names that may contain EPSG info
GRID_MAPPING_NAMES = [
    "polar_stereographic",
    "crs",
    "spatial_ref",
    "transverse_mercator",
    "lambert_conformal_conic",
    "albers_conical_equal_area",
    "mercator",
]

# Coordinate array names for x/y axes (CF convention)
X_COORDINATE_NAMES = ["xc", "x", "X"]
Y_COORDINATE_NAMES = ["yc", "y", "Y"]

# Attribute names that may contain EPSG codes
EPSG_ATTRIBUTE_NAMES = ["epsg_code", "epsg", "crs_epsg"]
