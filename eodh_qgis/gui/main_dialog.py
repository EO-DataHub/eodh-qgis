from __future__ import annotations

import os

from qgis.core import QgsApplication, QgsAuthMethodConfig
from qgis.PyQt import QtWidgets, uic

from eodh_qgis.gui.landing_widget import LandingWidget
from eodh_qgis.gui.overview_widget import OverviewWidget
from eodh_qgis.gui.process_widget import ProcessWidget
from eodh_qgis.gui.search_widget import SearchWidget
from eodh_qgis.gui.settings_widget import SettingsWidget
from eodh_qgis.settings import Settings

# Load the UI file
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), "../ui/main.ui"))


class MainDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, iface=None, parent=None):
        """Constructor.

        Args:
            iface: QGIS interface instance.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setupUi(self)

        self.iface = iface

        # Type hints for UI elements (from .ui file)
        self.tab_widget: QtWidgets.QTabWidget

        # Add initial tabs
        self.tab_widget.addTab(LandingWidget(parent=self), "Welcome")
        # Overview and Search tabs added after credential validation
        self.settings_widget = SettingsWidget(parent=self)
        self.tab_widget.addTab(self.settings_widget, "Settings")

        self.setup_ui_after_token()

    def get_creds(self) -> dict[str, str] | None:
        """Retrieve stored authentication credentials.

        Returns:
            A dictionary with 'token' and 'username' if available, else None.
        """
        settings = Settings()
        auth_config_id = settings.data["auth_config"]
        if not auth_config_id:
            return
        auth_mgr = QgsApplication.authManager()
        cfg = QgsAuthMethodConfig()
        auth_mgr.loadAuthenticationConfig(auth_config_id, cfg, True)
        creds = {
            "token": cfg.configMap().get("token"),
            "username": cfg.configMap().get("username"),
        }
        if not creds.get("token") or not creds.get("username"):
            return
        return creds

    def missing_creds(self):
        """Handle missing credentials by prompting the user to configure them."""
        settings_index = self.tab_widget.indexOf(self.settings_widget)
        self.tab_widget.setCurrentIndex(settings_index)
        QtWidgets.QMessageBox.warning(
            self,
            "Missing credentials",
            "Configure authentication settings",
        )

    def setup_ui_after_token(self):
        """Set up UI components that require authentication credentials."""
        self.creds = self.get_creds()
        if not self.creds:
            self.missing_creds()
            return

        # Add Overview and Search tabs
        self.overview_widget = OverviewWidget(creds=self.creds, parent=self)
        self.search_widget = SearchWidget(creds=self.creds, iface=self.iface, parent=self)

        # Connect overview catalogue selection to search widget
        self.overview_widget.catalogue_changed.connect(self.search_widget.set_catalog)
        # Connect overview collection selection to search widget
        self.overview_widget.collection_changed.connect(self.search_widget.set_collection)

        self.tab_widget.insertTab(1, self.overview_widget, "Overview")
        self.tab_widget.insertTab(2, self.search_widget, "Search")

        self.process_widget = ProcessWidget(creds=self.creds, parent=self)
        self.tab_widget.insertTab(3, self.process_widget, "Process")
