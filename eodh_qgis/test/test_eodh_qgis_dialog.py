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
