import os
import subprocess
import sys
from pathlib import Path
from typing import Literal

import pyeodh
import requests
from qgis.core import QgsApplication, QgsAuthMethodConfig
from qgis.PyQt import QtCore, QtWidgets, uic

from eodh_qgis.settings import Settings

# This loads your .ui file so that PyQt can populate your plugin with the elements from
# Qt Designer
FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/settings.ui")
)


class SettingsWidget(QtWidgets.QWidget, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(SettingsWidget, self).__init__(parent)
        self.setupUi(self)

        self.username_input: QtWidgets.QLineEdit
        self.token_input: QtWidgets.QLineEdit
        self.check_updates_on_start: QtWidgets.QCheckBox
        self.check_updates_button: QtWidgets.QPushButton
        self.settings = Settings()

        self.creds = parent.get_creds() or {}
        if self.creds:
            self.username_input.setText(self.creds.get("username", ""))
            self.token_input.setText(self.creds.get("token", ""))

        self.username_input.editingFinished.connect(lambda: self.save_creds("username"))
        self.token_input.editingFinished.connect(lambda: self.save_creds("token"))

        self.check_updates_on_start.setChecked(
            self.settings.data["check_update"] is True
        )
        self.check_updates_on_start.stateChanged.connect(
            lambda state: self.settings.save(
                "check_update", state == QtCore.Qt.CheckState.Checked
            )
        )

    def save_creds(self, key: Literal["username", "token"]):
        username = self.username_input.text()
        token = self.token_input.text()
        value = username if key == "username" else token
        if self.creds.get(key) == value:
            return

        if not value:
            return

        self.creds[key] = value

        cfg = QgsAuthMethodConfig("Basic")
        auth_config_id = self.settings.data["auth_config"]
        auth_mgr = QgsApplication.authManager()

        if not auth_config_id:
            cfg.setName("eodh_plugin")
            cfg.setConfigMap(self.creds)
            (res, cfg) = auth_mgr.storeAuthenticationConfig(cfg, True)
            if res:
                self.settings.save("auth_config", cfg.id())
                self.reload_ui()
            return

        (res, cfg) = auth_mgr.loadAuthenticationConfig(auth_config_id, cfg, True)
        if res:
            cfg.setConfigMap(self.creds)
            (res, cfg) = auth_mgr.storeAuthenticationConfig(cfg, True)
            if res:
                self.settings.save("auth_config", cfg.id())
                self.reload_ui()
        else:
            cfg.setName("eodh_plugin")
            cfg.setConfigMap(self.creds)
            (res, cfg) = auth_mgr.storeAuthenticationConfig(cfg, True)
            if res:
                self.settings.save("auth_config", cfg.id())
                self.reload_ui()

    def get_main_dialog(self):
        # Navigate up the parent hierarchy to find the main dialog
        parent = self.parent()
        while parent:
            if hasattr(parent, "setup_ui_after_token"):
                return parent
            parent = parent.parent()
        return None

    def reload_ui(self):
        if not self.creds.get("username") or not self.creds.get("token"):
            return
        main_dialog = self.get_main_dialog()
        if main_dialog:
            main_dialog.setup_ui_after_token()
