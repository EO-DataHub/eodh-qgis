"""Debug info dialog: everything support needs in one copyable report."""

from qgis.PyQt import QtGui, QtWidgets

from eodh_qgis import diagnostics

from .hub_widgets import button, label


class DebugDialog(QtWidgets.QDialog):
    def __init__(self, dock):
        super().__init__(dock)
        self.dock = dock
        self.setWindowTitle("EODH — Debug info")
        self.resize(780, 620)
        self.connectivity = {}
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(
            label("Copy this report into your support request. It never contains your workspace API key.")
        )
        self.text = QtWidgets.QPlainTextEdit()
        self.text.setReadOnly(True)
        # Wrapped, so a screenshot of the dialog shows whole lines.
        self.text.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.text.setFont(QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont))
        layout.addWidget(self.text, 1)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(button("Test connection again", self.test_connection))
        row.addStretch()
        self.copy_button = button("Copy to clipboard", self.copy)
        row.addWidget(self.copy_button)
        row.addWidget(button("Close", self.close))
        layout.addLayout(row)
        self.test_connection()

    def refresh(self):
        scroll = self.text.verticalScrollBar().value()
        self.text.setPlainText(diagnostics.report(self.dock, self.connectivity))
        self.text.verticalScrollBar().setValue(scroll)
        self.copy_button.setText("Copy to clipboard")

    def test_connection(self):
        for name, probe in diagnostics.PROBES.items():
            self.connectivity[name] = "testing…"

            def done(result, name=name):
                self.connectivity[name] = result
                self.refresh()

            def failed(error, name=name):
                done(f"failed: {diagnostics.describe(error)}", name)

            self.dock.submit(f"Testing {name}…", probe, done, failed, quiet=True)
        self.refresh()

    def copy(self):
        QtWidgets.QApplication.clipboard().setText(self.text.toPlainText())
        self.copy_button.setText("Copied")
