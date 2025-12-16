"""Asset type enumerations for EODH QGIS plugin."""

from enum import Enum


class AssetLayerType(Enum):
    """MIME types for STAC assets that can be loaded as layers."""

    COG = "image/tiff; application=geotiff; profile=cloud-optimized"
    GEOTIFF = "image/tiff; application=geotiff"
    TIFF = "image/tiff"
    NETCDF = "application/x-netcdf"
    NETCDF_ALT = "application/netcdf"
    PNG = "image/png"
    JPEG = "image/jpeg"


class AssetRole(Enum):
    """Standard STAC asset roles."""

    DATA = "data"
    THUMBNAIL = "thumbnail"
    OVERVIEW = "overview"
    METADATA = "metadata"
    VISUAL = "visual"


class FileType(Enum):
    """Display names for file types."""

    COG = "COG"
    GEOTIFF = "GeoTIFF"
    NETCDF = "NetCDF"
    PNG = "PNG"
    JPEG = "JPEG"
    XML = "XML"
    JSON = "JSON"
    TEXT = "Text"
    UNKNOWN = "Unknown"
