import os

from qgis.PyQt import QtWidgets, uic

# This loads your .ui file so that PyQt can populate your plugin with the elements from
# Qt Designer
FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/job_detail.ui")
)


class JobDetailsWidget(QtWidgets.QWidget, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(JobDetailsWidget, self).__init__(parent)
        self.setupUi(self)
        self.close_button.clicked.connect(self.handle_close)

    def handle_close(self):
        self.parent().removeWidget(self)
        self.parent().setCurrentIndex(1)
