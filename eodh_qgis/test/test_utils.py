"""Tests for utility functions."""

import os
import unittest

from osgeo import gdal

from eodh_qgis.utils import (
    extract_epsg_from_netcdf,
    get_netcdf_data_variables,
    get_netcdf_geotransform,
    get_netcdf_metadata,
    is_coordinate_variable,
)


class TestExtractEpsgFromNetcdf(unittest.TestCase):
    """Tests for extract_epsg_from_netcdf function."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = os.path.join(os.path.dirname(__file__), "data")
        self.netcdf_file = os.path.join(
            self.test_data_dir,
            "EOCIS-SEAICE-L3C-SITHICK-CS2-5KM-202302-fv1.0.nc",
        )

    def test_extract_epsg_from_netcdf_file(self):
        """Test extracting EPSG from a NetCDF file with polar_stereographic."""
        epsg = extract_epsg_from_netcdf(self.netcdf_file)
        self.assertEqual(epsg, "3413")

    def test_extract_epsg_from_netcdf_subdataset_format(self):
        """Test extracting EPSG when path is in NETCDF:"path":variable format."""
        netcdf_path = f'NETCDF:"{self.netcdf_file}":sea_ice_thickness'
        epsg = extract_epsg_from_netcdf(netcdf_path)
        self.assertEqual(epsg, "3413")

    def test_extract_epsg_nonexistent_file(self):
        """Test that nonexistent file returns None."""
        epsg = extract_epsg_from_netcdf("/nonexistent/file.nc")
        self.assertIsNone(epsg)

    def test_extract_epsg_invalid_path(self):
        """Test that invalid path returns None."""
        epsg = extract_epsg_from_netcdf("")
        self.assertIsNone(epsg)


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


class TestGetNetcdfDataVariables(unittest.TestCase):
    """Tests for get_netcdf_data_variables function."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = os.path.join(os.path.dirname(__file__), "data")
        self.netcdf_file = os.path.join(self.test_data_dir, "EOCIS-SEAICE-L3C-SITHICK-CS2-5KM-202302-fv1.0.nc")

    def test_returns_data_variables(self):
        """Test that data variables are returned."""
        variables = get_netcdf_data_variables(self.netcdf_file)
        var_names = [name for _, name in variables]

        # Should include data variables
        self.assertIn("sea_ice_thickness", var_names)
        self.assertIn("sea_ice_thickness_stdev", var_names)
        self.assertIn("n_thickness_measurements", var_names)

    def test_excludes_coordinate_variables(self):
        """Test that coordinate variables are excluded."""
        variables = get_netcdf_data_variables(self.netcdf_file)
        var_names = [name for _, name in variables]

        # Should exclude coordinates
        self.assertNotIn("lat", var_names)
        self.assertNotIn("lon", var_names)
        self.assertNotIn("time", var_names)
        self.assertNotIn("xc", var_names)
        self.assertNotIn("yc", var_names)
        self.assertNotIn("polar_stereographic", var_names)

    def test_excludes_bounds_variables(self):
        """Test that _bnds/_bounds variables are excluded."""
        variables = get_netcdf_data_variables(self.netcdf_file)
        var_names = [name for _, name in variables]

        # Should exclude bounds
        self.assertNotIn("time_bnds", var_names)

    def test_returns_subdataset_uris(self):
        """Test that subdataset URIs are properly formatted."""
        variables = get_netcdf_data_variables(self.netcdf_file)

        for uri, var_name in variables:
            # URI should contain the variable name
            self.assertIn(var_name, uri)
            # URI should be in NETCDF format
            self.assertTrue(uri.startswith("NETCDF:"))

    def test_nonexistent_file_returns_empty(self):
        """Test that nonexistent file returns empty list."""
        variables = get_netcdf_data_variables("/nonexistent/file.nc")
        self.assertEqual(variables, [])

    def test_empty_path_returns_empty(self):
        """Test that empty path returns empty list."""
        variables = get_netcdf_data_variables("")
        self.assertEqual(variables, [])


class TestGetNetcdfGeotransform(unittest.TestCase):
    """Tests for get_netcdf_geotransform function."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = os.path.join(os.path.dirname(__file__), "data")
        self.netcdf_file = os.path.join(
            self.test_data_dir,
            "EOCIS-SEAICE-L3C-SITHICK-CS2-5KM-202302-fv1.0.nc",
        )

    def test_returns_geotransform_tuple(self):
        """Test that a 6-element geotransform is returned."""
        gt = get_netcdf_geotransform(self.netcdf_file)
        self.assertIsNotNone(gt)
        self.assertEqual(len(gt), 6)

    def test_geotransform_has_negative_pixel_height(self):
        """Test that pixel height (element 5) is negative for north-up."""
        gt = get_netcdf_geotransform(self.netcdf_file)
        self.assertLess(gt[5], 0)

    def test_geotransform_zero_skew(self):
        """Test that skew elements are zero."""
        gt = get_netcdf_geotransform(self.netcdf_file)
        self.assertEqual(gt[2], 0.0)
        self.assertEqual(gt[4], 0.0)

    def test_nonexistent_file_returns_none(self):
        """Test that nonexistent file returns None."""
        gt = get_netcdf_geotransform("/nonexistent/file.nc")
        self.assertIsNone(gt)

    def test_subdataset_format(self):
        """Test with NETCDF:path:variable format."""
        path = f'NETCDF:"{self.netcdf_file}":sea_ice_thickness'
        gt = get_netcdf_geotransform(path)
        self.assertIsNotNone(gt)
        self.assertEqual(len(gt), 6)


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


if __name__ == "__main__":
    unittest.main()
