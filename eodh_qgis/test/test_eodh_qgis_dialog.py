from unittest.mock import patch

from qgis.PyQt import QtCore, QtWidgets
from qgis.testing import unittest
from .utilities import get_qgis_app

from eodh_qgis.gui.main_dialog import MainDialog


class EodhQgisDialogTest(unittest.TestCase):
    """Test dialog works."""

    @classmethod
    def setUpClass(cls):
        cls.QGIS_APP = get_qgis_app()
        assert cls.QGIS_APP is not None

    @patch("eodh_qgis.gui.main_dialog.MainDialog.setup_ui_after_token")
    @patch("eodh_qgis.gui.main_dialog.MainDialog.get_creds")
    def setUp(self, mock_get_creds, mock_setup_ui):
        """Runs before each test."""

        mock_get_creds.return_value = {"username": "test", "token": "test_token"}
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
        self.assertIsInstance(self.dialog.content_widget, QtWidgets.QStackedWidget)
        self.assertIsInstance(self.dialog.workflows_button, QtWidgets.QPushButton)
        self.assertIsInstance(self.dialog.jobs_button, QtWidgets.QPushButton)
        self.assertIsInstance(self.dialog.settings_button, QtWidgets.QPushButton)

    def test_initial_state(self):
        """Test the initial state of the dialog"""
        self.assertIsNone(self.dialog.selected_button)
        self.assertIsNone(self.dialog.ades_svc)

    def test_button_widget_map(self):
        """Test that the button_widget_map is correctly set up"""
        expected_keys = ["settings", "workflows", "jobs"]
        self.assertEqual(set(self.dialog.button_widget_map.keys()), set(expected_keys))

        for key in expected_keys:
            self.assertIn("button", self.dialog.button_widget_map[key])
            self.assertIn("widget", self.dialog.button_widget_map[key])

    def test_logo_cursor(self):
        """Test that the logo has the correct cursor"""
        self.assertEqual(
            self.dialog.logo.cursor().shape(), QtCore.Qt.CursorShape.PointingHandCursor
        )

    @patch("eodh_qgis.gui.main_dialog.QtWidgets.QMessageBox.warning")
    def test_missing_creds(self, mock_warning):
        """Test missing_creds method"""
        self.dialog.missing_creds()
        mock_warning.assert_called_once()
        self.assertEqual(self.dialog.selected_button, self.dialog.settings_button)
