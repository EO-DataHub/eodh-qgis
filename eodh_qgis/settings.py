from __future__ import annotations

from qgis.core import QgsApplication, QgsAuthMethodConfig
from qgis.PyQt import QtCore


class Settings:
    def __init__(self):
        self.group = "/eodh"
        self.data = {
            "auth_config": "",
            "env": "production",
        }
        self.load_all()

    def get_creds(self) -> dict[str, str] | None:
        """Retrieve stored authentication credentials from the QGIS auth manager.

        Returns:
            A dictionary with 'token' and 'username' if available, else None.
        """
        auth_config_id = self.data["auth_config"]
        if not auth_config_id:
            return None
        auth_mgr = QgsApplication.authManager()
        cfg = QgsAuthMethodConfig()
        auth_mgr.loadAuthenticationConfig(auth_config_id, cfg, True)
        creds = {
            "token": cfg.configMap().get("token"),
            "username": cfg.configMap().get("username"),
        }
        if not creds.get("token") or not creds.get("username"):
            return None
        return creds

    def load(self, key):
        qs = QtCore.QSettings()
        qs.beginGroup(self.group)
        value = qs.value(key)
        qs.endGroup()
        if value:
            self.data[key] = value

    def save(self, key, value):
        qs = QtCore.QSettings()
        qs.beginGroup(self.group)
        qs.setValue(key, value)
        qs.endGroup()

        self.load_all()

    def load_all(self):
        for k in self.data:
            self.load(k)
