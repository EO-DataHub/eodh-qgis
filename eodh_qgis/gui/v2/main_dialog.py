from qgis.core import QgsApplication, QgsAuthMethodConfig
from qgis.PyQt import QtCore, QtWidgets

from eodh_qgis.gui.settings_widget import SettingsWidget
from eodh_qgis.gui.v2.landing_widget import LandingWidget
from eodh_qgis.gui.v2.overview_widget import OverviewWidget
from eodh_qgis.gui.v2.search_widget import SearchWidget
from eodh_qgis.settings import Settings


class MainDialogV2(QtWidgets.QDialog):
    def __init__(self, parent=None):
        """Constructor."""
        super(MainDialogV2, self).__init__(parent)
        self.setWindowTitle("Earth Observation Data Hub")
        self.setMinimumSize(600, 500)

        main_layout = QtWidgets.QVBoxLayout()

        # Tab widget for navigation
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.addTab(LandingWidget(parent=self), "Welcome")
        # Overview and Search tabs added after credential validation
        self.tab_widget.addTab(self._create_placeholder_tab("Overview"), "Overview")
        self.tab_widget.addTab(self._create_placeholder_tab("Search"), "Search")
        self.tab_widget.addTab(self._create_placeholder_tab("Process"), "Process")
        self.tab_widget.addTab(self._create_placeholder_tab("View"), "View")
        self.settings_widget = SettingsWidget(parent=self)
        self.tab_widget.addTab(self.settings_widget, "Settings")
        main_layout.addWidget(self.tab_widget)

        self.setLayout(main_layout)

        self.setup_ui_after_token()

    def _create_placeholder_tab(self, name):
        """Create a placeholder tab."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        label = QtWidgets.QLabel(f"{name} - Coming soon")
        label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(label)
        widget.setLayout(layout)
        return widget

    def get_creds(self) -> dict[str, str]:
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
        settings_index = self.tab_widget.indexOf(self.settings_widget)
        self.tab_widget.setCurrentIndex(settings_index)
        QtWidgets.QMessageBox.warning(
            self,
            "Missing credentials",
            "Configure authentication settings",
        )

    def setup_ui_after_token(self):
        self.creds = self.get_creds()
        if not self.creds:
            self.missing_creds()
            return

        # Replace placeholder tabs with actual widgets
        self.overview_widget = OverviewWidget(creds=self.creds, parent=self)
        self.search_widget = SearchWidget(creds=self.creds, parent=self)

        # Connect overview catalogue selection to search widget
        self.overview_widget.catalogue_changed.connect(
            self.search_widget.set_catalog
        )

        # Remove placeholder and insert real widget at index 1 (Overview)
        self.tab_widget.removeTab(1)
        self.tab_widget.insertTab(1, self.overview_widget, "Overview")

        # Remove placeholder and insert real widget at index 2 (Search)
        self.tab_widget.removeTab(2)
        self.tab_widget.insertTab(2, self.search_widget, "Search")
