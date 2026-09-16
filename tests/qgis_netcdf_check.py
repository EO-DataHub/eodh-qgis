"""NetCDF regressions exercised through the current raster loader."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from osgeo import gdal
from qgis.core import QgsApplication, QgsRasterLayer
from qgis_test_support import finish

from eodh_qgis.layer_utils import get_netcdf_layers
from eodh_qgis.raster_loader import load_asset
from eodh_qgis.utils import get_netcdf_metadata, is_coordinate_variable

app = QgsApplication([], False)
app.initQgis()


class TestIsCoordinateVariable(unittest.TestCase):
    """Tests for is_coordinate_variable function."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = os.path.join(os.path.dirname(__file__), "data")
        self.netcdf_file = os.path.join(self.test_data_dir, "EOCIS-SEAICE-L3C-SITHICK-CS2-5KM-202302-fv1.0.nc")
        # Open file with multidim API
        self.md_ds = gdal.OpenEx(self.netcdf_file, gdal.OF_MULTIDIM_RASTER)
        self.root = self.md_ds.GetRootGroup() if self.md_ds else None

    def tearDown(self):
        """Clean up."""
        self.md_ds = None
        self.root = None

    def test_latitude_is_coordinate(self):
        """Test that lat (with standard_name=latitude) is detected as coordinate."""
        arr = self.root.OpenMDArray("lat")
        self.assertIsNotNone(arr)
        self.assertTrue(is_coordinate_variable(arr))

    def test_longitude_is_coordinate(self):
        """Test that lon (with standard_name=longitude) is detected as coordinate."""
        arr = self.root.OpenMDArray("lon")
        self.assertIsNotNone(arr)
        self.assertTrue(is_coordinate_variable(arr))

    def test_time_is_coordinate(self):
        """Test that time variable is detected as coordinate."""
        arr = self.root.OpenMDArray("time")
        self.assertIsNotNone(arr)
        self.assertTrue(is_coordinate_variable(arr))

    def test_xc_is_coordinate(self):
        """Test that xc (projection_x_coordinate) is detected as coordinate."""
        arr = self.root.OpenMDArray("xc")
        self.assertIsNotNone(arr)
        self.assertTrue(is_coordinate_variable(arr))

    def test_yc_is_coordinate(self):
        """Test that yc (projection_y_coordinate) is detected as coordinate."""
        arr = self.root.OpenMDArray("yc")
        self.assertIsNotNone(arr)
        self.assertTrue(is_coordinate_variable(arr))

    def test_polar_stereographic_is_coordinate(self):
        """Test that scalar grid_mapping variable is detected as coordinate."""
        arr = self.root.OpenMDArray("polar_stereographic")
        self.assertIsNotNone(arr)
        # Should be 0-dimensional (scalar), thus a coordinate
        self.assertTrue(is_coordinate_variable(arr))

    def test_sea_ice_thickness_is_data(self):
        """Test that sea_ice_thickness is detected as data variable."""
        arr = self.root.OpenMDArray("sea_ice_thickness")
        self.assertIsNotNone(arr)
        self.assertFalse(is_coordinate_variable(arr))

    def test_sea_ice_thickness_stdev_is_data(self):
        """Test that sea_ice_thickness_stdev is detected as data variable."""
        arr = self.root.OpenMDArray("sea_ice_thickness_stdev")
        self.assertIsNotNone(arr)
        self.assertFalse(is_coordinate_variable(arr))


class TestGetNetcdfMetadata(unittest.TestCase):
    """Tests for get_netcdf_metadata function."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = os.path.join(os.path.dirname(__file__), "data")
        self.netcdf_file = os.path.join(
            self.test_data_dir,
            "EOCIS-SEAICE-L3C-SITHICK-CS2-5KM-202302-fv1.0.nc",
        )

    def test_returns_metadata_object(self):
        """Test that metadata object is returned with all fields."""
        meta = get_netcdf_metadata(self.netcdf_file)
        self.assertIsNotNone(meta)
        self.assertIsInstance(meta.data_variables, list)

    def test_data_variables_found(self):
        """Test that data variables are extracted."""
        meta = get_netcdf_metadata(self.netcdf_file)
        var_names = [name for _, name in meta.data_variables]
        self.assertIn("sea_ice_thickness", var_names)

    def test_epsg_extracted(self):
        """Test that EPSG is extracted."""
        meta = get_netcdf_metadata(self.netcdf_file)
        self.assertEqual(meta.epsg, "3413")

    def test_geotransform_extracted(self):
        """Test that geotransform is extracted."""
        meta = get_netcdf_metadata(self.netcdf_file)
        self.assertIsNotNone(meta.geotransform)
        self.assertEqual(len(meta.geotransform), 6)

    def test_nonexistent_file(self):
        """Test that nonexistent file returns empty metadata."""
        meta = get_netcdf_metadata("/nonexistent/file.nc")
        self.assertEqual(meta.data_variables, [])
        self.assertIsNone(meta.geotransform)
        self.assertIsNone(meta.epsg)

    def test_subdataset_format(self):
        """Test with NETCDF:path:variable format."""
        path = f'NETCDF:"{self.netcdf_file}":sea_ice_thickness'
        meta = get_netcdf_metadata(path)
        self.assertIsNotNone(meta)
        self.assertIsInstance(meta.data_variables, list)


class TestGetNetcdfLayers(unittest.TestCase):
    """Tests for get_netcdf_layers function."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = os.path.join(os.path.dirname(__file__), "data")
        self.netcdf_file = os.path.join(
            self.test_data_dir,
            "EOCIS-SEAICE-L3C-SITHICK-CS2-5KM-202302-fv1.0.nc",
        )

    def test_loads_netcdf_variables(self):
        """Test loading data variables from real NetCDF file."""
        layers = get_netcdf_layers(self.netcdf_file, "test_layer")
        self.assertIsInstance(layers, list)
        self.assertGreater(len(layers), 0)
        for layer in layers:
            self.assertIsInstance(layer, QgsRasterLayer)
            self.assertTrue(layer.isValid())

    def test_selected_variables_filter(self):
        """Test filtering to specific variables."""
        layers = get_netcdf_layers(self.netcdf_file, "test_layer", selected_variables=["sea_ice_thickness"])
        self.assertEqual(len(layers), 1)
        self.assertIn("sea_ice_thickness", layers[0].name())

    def test_selected_variables_empty(self):
        """Test selecting no variables returns empty list."""
        layers = get_netcdf_layers(self.netcdf_file, "test_layer", selected_variables=[])
        self.assertEqual(len(layers), 0)

    def test_nonexistent_file_returns_empty(self):
        """Test nonexistent file returns empty list."""
        layers = get_netcdf_layers("/nonexistent/file.nc", "test")
        self.assertEqual(layers, [])

    def test_selected_nonexistent_variable(self):
        """Test selecting variable that doesn't exist returns empty."""
        layers = get_netcdf_layers(self.netcdf_file, "test_layer", selected_variables=["nonexistent_var"])
        self.assertEqual(len(layers), 0)


class TestCurrentNetcdfLoader(unittest.TestCase):
    def test_download_and_load_variables(self):
        fixture = Path(__file__).parent / "data/EOCIS-SEAICE-L3C-SITHICK-CS2-5KM-202302-fv1.0.nc"
        client = Mock()
        client.request.side_effect = lambda url, **kwargs: shutil.copyfile(fixture, kwargs["destination"])
        layers, streamed = load_asset(
            client, "https://example.test/ice.nc", {"type": "application/x-netcdf"}, "sea-ice"
        )
        try:
            self.assertFalse(streamed)
            self.assertTrue(layers)
            self.assertTrue(all(layer.isValid() for layer in layers))
            self.assertTrue(all(layer.crs().authid() == "EPSG:3413" for layer in layers))
        finally:
            layers.clear()
            Path(client.request.call_args.kwargs["destination"]).unlink()


result = unittest.TextTestRunner(verbosity=2).run(
    unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
)
finish(0 if result.wasSuccessful() else 1)
