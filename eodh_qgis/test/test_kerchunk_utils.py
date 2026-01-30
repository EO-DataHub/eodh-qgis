"""Tests for kerchunk parsing utilities."""

import os
import unittest

from eodh_qgis.kerchunk_utils import (
    NetCDFVariableInfo,
    _is_coordinate_variable_kerchunk,
    extract_epsg_from_kerchunk,
    extract_variables_from_kerchunk,
    get_geotransform_from_kerchunk,
    get_variable_display_info,
    is_kerchunk_file,
    load_variable_from_kerchunk,
    parse_kerchunk_json,
)


class TestIsKerchunkFile(unittest.TestCase):
    """Tests for is_kerchunk_file function."""

    def test_valid_kerchunk_structure(self):
        """Test that valid kerchunk structure is recognized."""
        data = {"version": 1, "refs": {".zgroup": "{}"}}
        self.assertTrue(is_kerchunk_file(data))

    def test_missing_refs_key(self):
        """Test that missing refs key is not recognized as kerchunk."""
        data = {"version": 1}
        self.assertFalse(is_kerchunk_file(data))

    def test_not_a_dict(self):
        """Test that non-dict is not recognized as kerchunk."""
        self.assertFalse(is_kerchunk_file([]))
        self.assertFalse(is_kerchunk_file("string"))
        self.assertFalse(is_kerchunk_file(None))


class TestParseKerchunkJson(unittest.TestCase):
    """Tests for parse_kerchunk_json function."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = os.path.join(os.path.dirname(__file__), "data")
        self.kerchunk_file = os.path.join(
            self.test_data_dir, "example_netcdf_kerchunk.json"
        )

    def test_parse_local_file(self):
        """Test parsing a local kerchunk JSON file."""
        data = parse_kerchunk_json(self.kerchunk_file)
        self.assertIsNotNone(data)
        self.assertIn("version", data)
        self.assertIn("refs", data)

    def test_parse_nonexistent_file(self):
        """Test that nonexistent file returns None."""
        data = parse_kerchunk_json("/nonexistent/file.json")
        self.assertIsNone(data)

    def test_parse_invalid_json(self):
        """Test that invalid JSON returns None."""
        # Create a temp file with invalid JSON
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json")
            temp_path = f.name

        try:
            data = parse_kerchunk_json(temp_path)
            self.assertIsNone(data)
        finally:
            os.unlink(temp_path)


class TestExtractVariablesFromKerchunk(unittest.TestCase):
    """Tests for extract_variables_from_kerchunk function."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = os.path.join(os.path.dirname(__file__), "data")
        self.kerchunk_file = os.path.join(
            self.test_data_dir, "example_netcdf_kerchunk.json"
        )
        self.kerchunk_data = parse_kerchunk_json(self.kerchunk_file)

    def test_extract_data_variables(self):
        """Test extracting data variables from kerchunk."""
        variables = extract_variables_from_kerchunk(self.kerchunk_data)
        var_names = [v.name for v in variables]

        # Should include data variables
        self.assertIn("sea_ice_thickness", var_names)
        self.assertIn("sea_ice_thickness_stdev", var_names)
        self.assertIn("n_thickness_measurements", var_names)

    def test_exclude_coordinate_variables(self):
        """Test that coordinate variables are excluded."""
        variables = extract_variables_from_kerchunk(self.kerchunk_data)
        var_names = [v.name for v in variables]

        # Should exclude coordinate variables
        self.assertNotIn("lat", var_names)
        self.assertNotIn("lon", var_names)
        self.assertNotIn("time", var_names)
        self.assertNotIn("xc", var_names)
        self.assertNotIn("yc", var_names)

    def test_exclude_grid_mapping_variables(self):
        """Test that grid mapping (scalar) variables are excluded."""
        variables = extract_variables_from_kerchunk(self.kerchunk_data)
        var_names = [v.name for v in variables]

        # Should exclude scalar grid mapping variable
        self.assertNotIn("polar_stereographic", var_names)

    def test_exclude_bounds_variables(self):
        """Test that bounds variables are excluded."""
        variables = extract_variables_from_kerchunk(self.kerchunk_data)
        var_names = [v.name for v in variables]

        # Should exclude bounds variables
        self.assertNotIn("time_bnds", var_names)

    def test_variable_metadata(self):
        """Test that variable metadata is correctly extracted."""
        variables = extract_variables_from_kerchunk(self.kerchunk_data)

        sit = next(v for v in variables if v.name == "sea_ice_thickness")
        self.assertEqual(sit.standard_name, "sea_ice_thickness")
        self.assertEqual(sit.units, "m")
        self.assertEqual(sit.long_name, "sea ice thickness")
        self.assertEqual(sit.shape, (1, 2240, 1520))
        self.assertEqual(sit.dimensions, ["time", "yc", "xc"])

    def test_empty_kerchunk(self):
        """Test handling of empty kerchunk data."""
        variables = extract_variables_from_kerchunk({"refs": {}})
        self.assertEqual(variables, [])


class TestGetVariableDisplayInfo(unittest.TestCase):
    """Tests for get_variable_display_info function."""

    def test_full_info(self):
        """Test display info with all metadata."""
        var = NetCDFVariableInfo(
            name="sea_ice_thickness",
            long_name="sea ice thickness",
            standard_name="sea_ice_thickness",
            units="m",
            shape=(1, 100, 100),
            dimensions=["time", "y", "x"],
        )
        display = get_variable_display_info(var)
        self.assertIn("sea_ice_thickness", display)
        self.assertIn("sea ice thickness", display)
        self.assertIn("(m)", display)
        self.assertIn("[1, 100, 100]", display)

    def test_minimal_info(self):
        """Test display info with minimal metadata."""
        var = NetCDFVariableInfo(
            name="data",
            long_name=None,
            standard_name=None,
            units=None,
            shape=(10, 20),
            dimensions=["y", "x"],
        )
        display = get_variable_display_info(var)
        self.assertIn("data", display)
        self.assertIn("[10, 20]", display)


class TestLoadVariableFromKerchunk(unittest.TestCase):
    """Tests for load_variable_from_kerchunk function."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = os.path.join(os.path.dirname(__file__), "data")
        self.kerchunk_file = os.path.join(
            self.test_data_dir, "example_netcdf_kerchunk.json"
        )
        self.kerchunk_data = parse_kerchunk_json(self.kerchunk_file)

    def test_load_existing_variable(self):
        """Test loading an existing variable returns data and attrs."""
        result = load_variable_from_kerchunk(self.kerchunk_data, "sea_ice_thickness")
        self.assertIsNotNone(result)
        data, attrs = result
        self.assertEqual(len(data.shape), 3)  # (time, yc, xc)
        self.assertIn("units", attrs)

    def test_load_nonexistent_variable(self):
        """Test loading a nonexistent variable returns None."""
        result = load_variable_from_kerchunk(self.kerchunk_data, "nonexistent_var")
        self.assertIsNone(result)

    def test_load_invalid_kerchunk(self):
        """Test loading from invalid kerchunk returns None."""
        result = load_variable_from_kerchunk({"refs": {}}, "sea_ice_thickness")
        self.assertIsNone(result)


class TestGetGeotransformFromKerchunk(unittest.TestCase):
    """Tests for get_geotransform_from_kerchunk function."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = os.path.join(os.path.dirname(__file__), "data")
        self.kerchunk_file = os.path.join(
            self.test_data_dir, "example_netcdf_kerchunk.json"
        )
        self.kerchunk_data = parse_kerchunk_json(self.kerchunk_file)

    def test_extract_geotransform(self):
        """Test extracting geotransform from kerchunk with xc/yc."""
        gt = get_geotransform_from_kerchunk(self.kerchunk_data)
        self.assertIsNotNone(gt)
        self.assertEqual(len(gt), 6)

    def test_geotransform_negative_pixel_height(self):
        """Test pixel height is negative for north-up."""
        gt = get_geotransform_from_kerchunk(self.kerchunk_data)
        self.assertLess(gt[5], 0)

    def test_geotransform_zero_skew(self):
        """Test skew elements are zero."""
        gt = get_geotransform_from_kerchunk(self.kerchunk_data)
        self.assertEqual(gt[2], 0.0)
        self.assertEqual(gt[4], 0.0)

    def test_empty_kerchunk_returns_none(self):
        """Test empty kerchunk returns None."""
        gt = get_geotransform_from_kerchunk({"refs": {}})
        self.assertIsNone(gt)


class TestIsCoordinateVariableKerchunk(unittest.TestCase):
    """Tests for _is_coordinate_variable_kerchunk function."""

    def test_scalar_variable_is_coordinate(self):
        """Test that 0-dimensional (scalar) variables are coordinates."""
        zattrs = {}
        zarray = {"shape": []}
        self.assertTrue(_is_coordinate_variable_kerchunk(zattrs, zarray))

    def test_standard_name_latitude(self):
        """Test that latitude standard_name is coordinate."""
        zattrs = {"standard_name": "latitude"}
        zarray = {"shape": [100]}
        self.assertTrue(_is_coordinate_variable_kerchunk(zattrs, zarray))

    def test_standard_name_longitude(self):
        """Test that longitude standard_name is coordinate."""
        zattrs = {"standard_name": "longitude"}
        zarray = {"shape": [200]}
        self.assertTrue(_is_coordinate_variable_kerchunk(zattrs, zarray))

    def test_standard_name_time(self):
        """Test that time standard_name is coordinate."""
        zattrs = {"standard_name": "time"}
        zarray = {"shape": [12]}
        self.assertTrue(_is_coordinate_variable_kerchunk(zattrs, zarray))

    def test_standard_name_projection_x(self):
        """Test that projection_x_coordinate is coordinate."""
        zattrs = {"standard_name": "projection_x_coordinate"}
        zarray = {"shape": [1520]}
        self.assertTrue(_is_coordinate_variable_kerchunk(zattrs, zarray))

    def test_axis_attribute_is_coordinate(self):
        """Test that variables with axis attribute are coordinates."""
        zattrs = {"axis": "X"}
        zarray = {"shape": [100]}
        self.assertTrue(_is_coordinate_variable_kerchunk(zattrs, zarray))

    def test_data_variable_is_not_coordinate(self):
        """Test that a regular data variable is not coordinate."""
        zattrs = {"long_name": "sea ice thickness", "units": "m"}
        zarray = {"shape": [1, 2240, 1520]}
        self.assertFalse(_is_coordinate_variable_kerchunk(zattrs, zarray))

    def test_missing_shape_is_coordinate(self):
        """Test that missing shape (treated as scalar) is coordinate."""
        zattrs = {}
        zarray = {}
        self.assertTrue(_is_coordinate_variable_kerchunk(zattrs, zarray))


class TestExtractEpsgFromKerchunk(unittest.TestCase):
    """Tests for extract_epsg_from_kerchunk function."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = os.path.join(os.path.dirname(__file__), "data")
        self.kerchunk_file = os.path.join(
            self.test_data_dir, "example_netcdf_kerchunk.json"
        )
        self.kerchunk_data = parse_kerchunk_json(self.kerchunk_file)

    def test_extract_epsg_from_real_kerchunk(self):
        """Test extracting EPSG from the test kerchunk file."""
        epsg = extract_epsg_from_kerchunk(self.kerchunk_data)
        self.assertEqual(epsg, "3413")

    def test_extract_epsg_with_crs_variable(self):
        """Test extracting EPSG from a crs grid_mapping variable."""
        data = {
            "refs": {
                "crs/.zattrs": '{"epsg_code": 4326}',
            }
        }
        self.assertEqual(extract_epsg_from_kerchunk(data), "4326")

    def test_extract_epsg_with_epsg_attr(self):
        """Test extracting EPSG from epsg attribute name."""
        data = {
            "refs": {
                "spatial_ref/.zattrs": '{"epsg": 32632}',
            }
        }
        self.assertEqual(extract_epsg_from_kerchunk(data), "32632")

    def test_no_epsg_returns_none(self):
        """Test that missing EPSG returns None."""
        data = {"refs": {}}
        self.assertIsNone(extract_epsg_from_kerchunk(data))

    def test_invalid_json_zattrs(self):
        """Test that invalid JSON in zattrs is handled."""
        data = {
            "refs": {
                "crs/.zattrs": "not valid json",
            }
        }
        self.assertIsNone(extract_epsg_from_kerchunk(data))


if __name__ == "__main__":
    unittest.main()
