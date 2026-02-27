from unittest.mock import patch

from qgis.PyQt import QtWidgets
from qgis.testing import unittest

from eodh_qgis.gui.main_dialog import MainDialog

from .utilities import get_qgis_app


class EodhQgisDialogTest(unittest.TestCase):
    """Test dialog works."""

    @classmethod
    def setUpClass(cls):
        cls.QGIS_APP = get_qgis_app()
        assert cls.QGIS_APP is not None

    @patch("eodh_qgis.gui.main_dialog.MainDialog.setup_ui_after_token")
    def setUp(self, mock_setup_ui):
        """Runs before each test."""
        self.dialog = MainDialog()

    def tearDown(self):
        """Runs after each test."""
        self.dialog = None

    def test_dialog_creation(self):
        """Test that the dialog is created successfully"""
        self.assertIsNotNone(self.dialog)
        self.assertIsInstance(self.dialog, MainDialog)

    def test_ui_elements_exist(self):
        """Test that essential UI elements are present"""
        self.assertIsInstance(self.dialog.tab_widget, QtWidgets.QTabWidget)
        self.assertIsInstance(self.dialog.settings_widget, QtWidgets.QWidget)

    def test_initial_state(self):
        """Test the initial state of the dialog"""
        self.assertIsNone(self.dialog.iface)

    @patch("eodh_qgis.gui.main_dialog.QtWidgets.QMessageBox.warning")
    def test_missing_creds(self, mock_warning):
        """Test missing_creds method"""
        self.dialog.missing_creds()
        mock_warning.assert_called_once()
        # Should switch to settings tab
        settings_index = self.dialog.tab_widget.indexOf(self.dialog.settings_widget)
        self.assertEqual(self.dialog.tab_widget.currentIndex(), settings_index)

    @patch("eodh_qgis.gui.main_dialog.MainDialog.get_creds")
    def test_setup_ui_after_token_no_tab_duplication(self, mock_get_creds):
        """Test that calling setup_ui_after_token multiple times does not duplicate tabs."""
        mock_get_creds.return_value = {"username": "user", "token": "tok"}

        # Call setup twice (simulates credential update)
        self.dialog.setup_ui_after_token()
        self.dialog.setup_ui_after_token()

        tab_names = [self.dialog.tab_widget.tabText(i) for i in range(self.dialog.tab_widget.count())]
        # Should have exactly one of each, not duplicates
        self.assertEqual(tab_names.count("Overview"), 1)
        self.assertEqual(tab_names.count("Search"), 1)
        self.assertEqual(tab_names.count("Process"), 1)
