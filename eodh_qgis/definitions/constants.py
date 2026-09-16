"""Plugin-wide constants for EODH QGIS."""

# Plugin metadata
PLUGIN_NAME = "EODH"

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
