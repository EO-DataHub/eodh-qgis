"""NetCDF regressions, using a disposable copy so GDAL cannot alter the fixture."""

import shutil
from pathlib import Path
from unittest.mock import Mock

import pytest
from osgeo import gdal
from qgis.core import QgsRasterLayer

from eodh_qgis.layer_utils import get_netcdf_layers
from eodh_qgis.raster_loader import load_asset
from eodh_qgis.utils import get_netcdf_metadata, is_coordinate_variable


@pytest.fixture
def netcdf_file(tmp_path):
    source = Path(__file__).parents[1] / "data/EOCIS-SEAICE-L3C-SITHICK-CS2-5KM-202302-fv1.0.nc"
    return str(shutil.copyfile(source, tmp_path / "sea-ice.nc"))


@pytest.fixture
def netcdf_root(netcdf_file):
    dataset = gdal.OpenEx(netcdf_file, gdal.OF_MULTIDIM_RASTER)
    root = dataset.GetRootGroup()
    yield root
    root = dataset = None


@pytest.mark.parametrize(
    ("variable", "coordinate"),
    [
        ("lat", True),
        ("lon", True),
        ("time", True),
        ("xc", True),
        ("yc", True),
        ("polar_stereographic", True),
        ("sea_ice_thickness", False),
        ("sea_ice_thickness_stdev", False),
    ],
)
def test_coordinate_detection(netcdf_root, variable, coordinate):
    array = netcdf_root.OpenMDArray(variable)
    assert array is not None
    assert is_coordinate_variable(array) is coordinate


@pytest.mark.parametrize("subdataset", [False, True])
def test_metadata_contains_data_variables_crs_and_geotransform(netcdf_file, subdataset):
    path = f'NETCDF:"{netcdf_file}":sea_ice_thickness' if subdataset else netcdf_file
    metadata = get_netcdf_metadata(path)
    assert isinstance(metadata.data_variables, list)
    assert "sea_ice_thickness" in [name for _, name in metadata.data_variables]
    assert metadata.epsg == "3413"
    assert metadata.geotransform is not None
    assert len(metadata.geotransform) == 6


def test_nonexistent_file_returns_empty_metadata_and_layers(tmp_path):
    path = str(tmp_path / "missing.nc")
    metadata = get_netcdf_metadata(path)
    assert metadata.data_variables == []
    assert metadata.epsg is None
    assert metadata.geotransform is None
    assert get_netcdf_layers(path, "test") == []


def test_loads_valid_raster_layers(netcdf_file):
    layers = get_netcdf_layers(netcdf_file, "test")
    assert layers
    assert all(isinstance(layer, QgsRasterLayer) and layer.isValid() for layer in layers)


@pytest.mark.parametrize(("selected", "count"), [(["sea_ice_thickness"], 1), ([], 0), (["missing"], 0)])
def test_variable_selection(netcdf_file, selected, count):
    layers = get_netcdf_layers(netcdf_file, "test", selected_variables=selected)
    assert len(layers) == count
    if layers:
        assert "sea_ice_thickness" in layers[0].name()


def test_asset_loader_downloads_and_loads_variables(netcdf_file):
    client = Mock()
    client.request.side_effect = lambda url, **kwargs: shutil.copyfile(netcdf_file, kwargs["destination"])
    layers, streamed = load_asset(client, "https://example.test/ice.nc", {"type": "application/x-netcdf"}, "sea-ice")
    try:
        assert not streamed
        assert layers
        assert all(layer.isValid() for layer in layers)
        assert all(layer.crs().authid() == "EPSG:3413" for layer in layers)
    finally:
        layers.clear()
        Path(client.request.call_args.kwargs["destination"]).unlink()
