import unittest
from unittest.mock import patch
from eodh_qgis.settings import Settings


class TestSettings(unittest.TestCase):

    def setUp(self):
        self.settings = Settings()

    @patch("eodh_qgis.settings.QtCore.QSettings")
    def test_load(self, mock_qsettings):
        # Mock the QSettings.value method to return a test value
        mock_qsettings.return_value.value.return_value = "test_value"

        self.settings.load("auth_config")

        self.assertEqual(self.settings.data["auth_config"], "test_value")
        mock_qsettings.return_value.beginGroup.assert_called_once_with("/eodh")
        mock_qsettings.return_value.value.assert_called_once_with("auth_config")
        mock_qsettings.return_value.endGroup.assert_called_once()

    @patch("eodh_qgis.settings.QtCore.QSettings")
    def test_save(self, mock_qsettings):
        self.settings.save("auth_config", "new_value")

        mock_qsettings.return_value.beginGroup.assert_called_with("/eodh")
        mock_qsettings.return_value.setValue.assert_called_with(
            "auth_config", "new_value"
        )
        mock_qsettings.return_value.endGroup.assert_called()

    @patch.object(Settings, "load")
    def test_load_all(self, mock_load):
        self.settings.load_all()

        # Check if load was called for each key in self.data
        self.assertEqual(mock_load.call_count, len(self.settings.data))
        for key in self.settings.data:
            mock_load.assert_any_call(key)

    def test_initial_values(self):
        self.assertEqual(self.settings.group, "/eodh")
        self.assertIn("auth_config", self.settings.data)
        self.assertIn("check_update", self.settings.data)
