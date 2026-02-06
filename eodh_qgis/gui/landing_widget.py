import os

from qgis.PyQt import QtWidgets, uic

# Load the UI file
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), "../ui/landing.ui"))


class LandingWidget(QtWidgets.QWidget, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(parent)
        self.setupUi(self)

        # Type hints for UI elements (from .ui file)
        self.main_frame: QtWidgets.QFrame
        self.logo_label: QtWidgets.QLabel
        self.title_label: QtWidgets.QLabel
        self.hello_group: QtWidgets.QGroupBox
        self.hello_label: QtWidgets.QLabel
        self.howto_group: QtWidgets.QGroupBox
        self.howto_label: QtWidgets.QLabel
        self.docs_group: QtWidgets.QGroupBox
        self.docs_label: QtWidgets.QLabel
