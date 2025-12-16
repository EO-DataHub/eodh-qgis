"""Tests for variable selection dialog."""

import unittest

from eodh_qgis.gui.variable_selection_dialog import VariableSelectionDialog
from eodh_qgis.kerchunk_utils import NetCDFVariableInfo


class TestVariableSelectionDialog(unittest.TestCase):
    """Tests for VariableSelectionDialog."""

    def _make_variables(self):
        """Create sample variable list."""
        return [
            NetCDFVariableInfo(
                name="sea_ice_thickness",
                long_name="sea ice thickness",
                standard_name="sea_ice_thickness",
                units="m",
                shape=(1, 2240, 1520),
                dimensions=["time", "yc", "xc"],
            ),
            NetCDFVariableInfo(
                name="sea_ice_thickness_stdev",
                long_name="standard deviation",
                standard_name=None,
                units="m",
                shape=(1, 2240, 1520),
                dimensions=["time", "yc", "xc"],
            ),
            NetCDFVariableInfo(
                name="n_thickness_measurements",
                long_name="number of measurements",
                standard_name=None,
                units=None,
                shape=(1, 2240, 1520),
                dimensions=["time", "yc", "xc"],
            ),
        ]

    def test_dialog_creation(self):
        """Test dialog is created with correct number of checkboxes."""
        variables = self._make_variables()
        dialog = VariableSelectionDialog(variables, "item-1", "data")

        self.assertEqual(len(dialog._checkboxes), 3)
        self.assertEqual(dialog.windowTitle(), "Select Variables - item-1")

    def test_all_selected_by_default(self):
        """Test all variables are selected by default."""
        variables = self._make_variables()
        dialog = VariableSelectionDialog(variables, "item-1", "data")

        selected = dialog.get_selected_variables()
        self.assertEqual(len(selected), 3)
        self.assertIn("sea_ice_thickness", selected)

    def test_deselect_all(self):
        """Test deselect all unchecks everything."""
        variables = self._make_variables()
        dialog = VariableSelectionDialog(variables, "item-1", "data")

        dialog._deselect_all()
        selected = dialog.get_selected_variables()
        self.assertEqual(len(selected), 0)

    def test_select_all_after_deselect(self):
        """Test select all after deselect restores all."""
        variables = self._make_variables()
        dialog = VariableSelectionDialog(variables, "item-1", "data")

        dialog._deselect_all()
        dialog._select_all()
        selected = dialog.get_selected_variables()
        self.assertEqual(len(selected), 3)

    def test_partial_selection(self):
        """Test manually unchecking one variable."""
        variables = self._make_variables()
        dialog = VariableSelectionDialog(variables, "item-1", "data")

        # Uncheck first checkbox
        dialog._checkboxes[0][0].setChecked(False)
        selected = dialog.get_selected_variables()
        self.assertEqual(len(selected), 2)
        self.assertNotIn("sea_ice_thickness", selected)

    def test_tooltip_content(self):
        """Test tooltip contains variable info."""
        var = self._make_variables()[0]
        dialog = VariableSelectionDialog([var], "item-1", "data")

        tooltip = dialog._build_tooltip(var)
        self.assertIn("sea_ice_thickness", tooltip)
        self.assertIn("sea ice thickness", tooltip)
        self.assertIn("m", tooltip)
        self.assertIn("Shape", tooltip)

    def test_tooltip_minimal_info(self):
        """Test tooltip with minimal variable info."""
        var = NetCDFVariableInfo(
            name="data",
            long_name=None,
            standard_name=None,
            units=None,
            shape=(10,),
            dimensions=["x"],
        )
        dialog = VariableSelectionDialog([var], "item-1", "data")

        tooltip = dialog._build_tooltip(var)
        self.assertIn("data", tooltip)
        self.assertNotIn("Long name", tooltip)
        self.assertNotIn("Units", tooltip)

    def test_empty_variables(self):
        """Test dialog with no variables."""
        dialog = VariableSelectionDialog([], "item-1", "data")
        self.assertEqual(len(dialog._checkboxes), 0)
        self.assertEqual(dialog.get_selected_variables(), [])


if __name__ == "__main__":
    unittest.main()
