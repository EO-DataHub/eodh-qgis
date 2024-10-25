import unittest
from unittest.mock import MagicMock, patch
from qgis.PyQt.QtWidgets import QApplication, QWidget
from qgis.PyQt.QtCore import Qt
from eodh_qgis.gui.settings_widget import SettingsWidget
from eodh_qgis.settings import Settings


class TestSettingsWidget(unittest.TestCase):

    def setUp(self):
        self.parent = QWidget()
        self.parent.get_creds = MagicMock(
            return_value={
                "username": "test_user",
                "token": "test_token",
            }
        )
        self.widget = SettingsWidget(self.parent)

    def tearDown(self):
        self.widget.deleteLater()
        self.parent.deleteLater()

    def test_init(self):
        self.assertIsInstance(self.widget, SettingsWidget)
        self.assertEqual(self.widget.username_input.text(), "test_user")
        self.assertEqual(self.widget.token_input.text(), "test_token")

    @patch("eodh_qgis.gui.settings_widget.Settings")
    def test_check_updates_on_start(self, mock_settings):
        mock_settings_instance = mock_settings.return_value
        mock_settings_instance.data = {"check_update": True}

        widget = SettingsWidget(self.parent)
        self.assertTrue(widget.check_updates_on_start.isChecked())

        widget.check_updates_on_start.setChecked(False)
        mock_settings_instance.save.assert_called_with("check_update", False)

    @patch("eodh_qgis.gui.settings_widget.QgsApplication")
    @patch("eodh_qgis.gui.settings_widget.QgsAuthMethodConfig")
    def test_save_creds(self, mock_auth_config, mock_qgs_app):
        mock_auth_mgr = MagicMock()
        mock_qgs_app.authManager.return_value = mock_auth_mgr
        mock_auth_mgr.loadAuthenticationConfig.return_value = (True, MagicMock())
        mock_auth_mgr.storeAuthenticationConfig.return_value = (True, MagicMock())

        self.widget.settings = MagicMock()
        self.widget.settings.data = {"auth_config": "test_config_id"}

        # Mock the get_main_dialog method
        mock_main_dialog = MagicMock()
        self.widget.get_main_dialog = MagicMock(return_value=mock_main_dialog)

        self.widget.username_input.setText("new_user")
        self.widget.save_creds("username")

        mock_auth_mgr.loadAuthenticationConfig.assert_called_once()
        mock_auth_mgr.storeAuthenticationConfig.assert_called_once()
        self.assertEqual(self.widget.creds["username"], "new_user")
        mock_main_dialog.setup_ui_after_token.assert_called_once()

    def test_reload_ui(self):
        self.widget.creds = {"username": "test_user", "token": "test_token"}

        # Mock the get_main_dialog method
        mock_main_dialog = MagicMock()
        self.widget.get_main_dialog = MagicMock(return_value=mock_main_dialog)

        self.widget.reload_ui()

        mock_main_dialog.setup_ui_after_token.assert_called_once()


if __name__ == "__main__":
    unittest.main()
