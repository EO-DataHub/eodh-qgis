import os

import pyeodh
import pyeodh.ades
import requests
from qgis.PyQt import QtWidgets, uic

# This loads your .ui file so that PyQt can populate your plugin with the elements from
# Qt Designer
FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/login_dialog.ui")
)


class LoginDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(LoginDialog, self).__init__(parent)
        self.setupUi(self)
        self.ades_svc = None

        self.username_input: QtWidgets.QLineEdit
        self.password_input: QtWidgets.QLineEdit
        self.login_btn: QtWidgets.QPushButton
        self.login_btn.clicked.connect(self.login)

    def lock_form(self, locked: bool):
        self.username_input.setEnabled(not locked)
        self.password_input.setEnabled(not locked)
        self.login_btn.setEnabled(not locked)

    def login(self):
        self.lock_form(True)
        self.username = self.username_input.text() or os.getenv("ADES_USERNAME")
        self.password = self.password_input.text() or os.getenv("ADES_PASSWORD")

        try:
            self.ades_svc = pyeodh.Client(
                auth=(self.username, self.password)
            ).get_ades()
        except requests.HTTPError:
            QtWidgets.QMessageBox.critical(
                self, "Error", "Error logging in, service unavailable."
            )

        self.close()
