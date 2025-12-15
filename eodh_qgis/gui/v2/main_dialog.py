import pyeodh
from qgis.core import QgsApplication, QgsAuthMethodConfig
from qgis.PyQt import QtCore, QtWidgets

from eodh_qgis.gui.settings_widget import SettingsWidget
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
        self.tab_widget.addTab(self._create_overview_tab(), "Overview")
        self.tab_widget.addTab(self._create_search_tab(), "Search")
        self.tab_widget.addTab(self._create_placeholder_tab("Process"), "Process")
        self.tab_widget.addTab(self._create_placeholder_tab("View"), "View")
        self.settings_widget = SettingsWidget(parent=self)
        self.tab_widget.addTab(self.settings_widget, "Settings")
        main_layout.addWidget(self.tab_widget)

        self.setLayout(main_layout)

        self.setup_ui_after_token()

    def _create_overview_tab(self):
        """Create the Overview tab with intro content."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()

        # Hello section
        hello_group = QtWidgets.QGroupBox()
        hello_layout = QtWidgets.QVBoxLayout()
        hello_label = QtWidgets.QLabel("Hello. This is all about the EODH")
        hello_label.setAlignment(QtCore.Qt.AlignCenter)
        hello_layout.addWidget(hello_label)
        hello_group.setLayout(hello_layout)
        layout.addWidget(hello_group)

        # How to use section
        howto_group = QtWidgets.QGroupBox()
        howto_layout = QtWidgets.QVBoxLayout()
        howto_label = QtWidgets.QLabel("This is how to use this plugin")
        howto_label.setAlignment(QtCore.Qt.AlignCenter)
        howto_layout.addWidget(howto_label)
        howto_group.setLayout(howto_layout)
        layout.addWidget(howto_group, 1)

        # Documentation links section
        docs_group = QtWidgets.QGroupBox()
        docs_layout = QtWidgets.QVBoxLayout()
        docs_label = QtWidgets.QLabel("Links to documentation")
        docs_label.setAlignment(QtCore.Qt.AlignCenter)
        docs_layout.addWidget(docs_label)
        docs_group.setLayout(docs_layout)
        layout.addWidget(docs_group)

        widget.setLayout(layout)
        return widget

    def _create_search_tab(self):
        """Create the Search tab."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()

        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Enter search term...")
        layout.addWidget(self.search_input)

        self.search_button = QtWidgets.QPushButton("Search")
        self.search_button.clicked.connect(self.on_search_clicked)
        layout.addWidget(self.search_button)

        self.results_text = QtWidgets.QTextEdit()
        self.results_text.setReadOnly(True)
        layout.addWidget(self.results_text)

        widget.setLayout(layout)
        return widget

    def _create_placeholder_tab(self, name):
        """Create a placeholder tab."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        label = QtWidgets.QLabel(f"{name} - Coming soon")
        label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(label)
        widget.setLayout(layout)
        return widget

    def on_search_clicked(self):
        search_term = self.search_input.text()
        if not search_term:
            return

        self.results_text.clear()
        self.results_text.append(f"Searching for: {search_term}...")

        try:
            client = pyeodh.Client(
                username=self.creds["username"], token=self.creds["token"]
            )
            catalog_service = client.get_catalog_service()
            results = catalog_service.collection_search(query=search_term, limit=10)

            self.results_text.clear()
            count = 0
            for item in results:
                count += 1
                self.results_text.append(
                    f"{count}. {item.id} - {item.title or 'No title'}"
                )

            if count == 0:
                self.results_text.append("No results found.")
        except Exception as e:
            self.results_text.append(f"Error: {str(e)}")

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
