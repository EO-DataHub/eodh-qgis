import os
from typing import Optional

import pyeodh.ades
import requests
from qgis.PyQt import Qsci, QtGui, QtWidgets, uic

# This loads your .ui file so that PyQt can populate your plugin with the elements from
# Qt Designer
FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "../../ui/wf_editor.ui")
)


class YAMLEditor(Qsci.QsciScintilla):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLexer(Qsci.QsciLexerYAML(self))
        self.setTabWidth(2)
        self.setAutoIndent(True)
        self.setIndentationsUseTabs(False)
        self.setIndentationGuides(True)
        self.setIndentationWidth(2)


class WorkflowEditorWidget(QtWidgets.QWidget, FORM_CLASS):
    def __init__(
        self,
        ades_svc: pyeodh.ades.Ades,
        update_mode=False,
        process: Optional[pyeodh.ades.Process] = None,
        parent=None,
    ):
        """Constructor."""
        super(WorkflowEditorWidget, self).__init__(parent)
        self.setupUi(self)
        self.ades_svc = ades_svc
        self.update_mode = update_mode
        self.process = process

        self.content_widget: QtWidgets.QStackedWidget
        self.cwl_url_button: QtWidgets.QRadioButton
        self.cwl_yaml_button: QtWidgets.QRadioButton
        self.cancel_button: QtWidgets.QPushButton
        self.deploy_button: QtWidgets.QPushButton
        self.cwl_url_input: QtWidgets.QLineEdit
        self.proc_label: QtWidgets.QLabel
        self.cwl_url_button.page_index = 0
        self.cwl_yaml_button.page_index = 1

        self.cwl_url_button.toggled.connect(self.handle_radio)
        self.cwl_yaml_button.toggled.connect(self.handle_radio)
        self.cancel_button.clicked.connect(self.handle_cancel)
        self.deploy_button.clicked.connect(self.handle_deploy)

        self.cwl_url_input.textEdited.connect(self.handle_url_input)
        self.yaml_editor = YAMLEditor()
        self.yaml_editor.textChanged.connect(self.handle_yaml_input)
        self.content_widget.insertWidget(1, self.yaml_editor)
        self.content_widget.setCurrentIndex(0)

        if self.update_mode and self.process is not None:
            self.proc_label.setText(f"**Process ID**:    `{self.process.id}`")
        else:
            self.proc_label.hide()

    def handle_radio(self):
        btn: QtWidgets.QRadioButton = self.sender()
        if btn.isChecked():
            self.content_widget.setCurrentIndex(btn.page_index)
            btn.setFont(
                QtGui.QFont(
                    "Fira Sans",
                    pointSize=11,
                    weight=QtGui.QFont.Bold,
                )
            )
            if btn.page_index == 0:
                self.handle_url_input()
            elif btn.page_index == 1:
                self.handle_yaml_input()
        else:
            btn.setFont(
                QtGui.QFont(
                    "Fira Sans",
                    pointSize=11,
                    weight=QtGui.QFont.Normal,
                )
            )

    def handle_cancel(self):
        self.parent().removeWidget(self)
        self.parent().setCurrentIndex(0)

    def handle_url_input(self):
        if self.cwl_url_input.text():
            self.deploy_button.setEnabled(True)
        else:
            self.deploy_button.setEnabled(False)

    def handle_yaml_input(self):
        if self.yaml_editor.text():
            self.deploy_button.setEnabled(True)
        else:
            self.deploy_button.setEnabled(False)

    def handle_deploy(self):
        self.lock_form(True)
        idx = self.content_widget.currentIndex()
        kwargs = {
            "cwl_url": None,
            "cwl_yaml": None,
        }
        if idx == 0:
            text = self.cwl_url_input.text()
            if not text:
                QtWidgets.QMessageBox.warning(self, "Error", "Missing URL input!")
                self.lock_form(False)
                return
            kwargs["cwl_url"] = text
        elif idx == 1:
            text = self.yaml_editor.text()
            if not text:
                QtWidgets.QMessageBox.warning(self, "Error", "Missing YAML input!")
                self.lock_form(False)
                return
            kwargs["cwl_yaml"] = text
        try:
            if self.update_mode and self.process is not None:
                self.process.update(**kwargs)
                proc = self.process
            else:
                proc = self.ades_svc.deploy_process(**kwargs)
        except requests.HTTPError as e:
            QtWidgets.QMessageBox.critical(
                self, "Error", f"Error deploying process!\n{e}"
            )
        else:
            self.parent().parent().parent().workflows_widget.load_workflows()
            QtWidgets.QMessageBox.information(
                self, "Success", f"Successfully deployed {proc.id}."
            )
            self.handle_cancel()

    def lock_form(self, locked: bool):
        self.cwl_url_button.setEnabled(not locked)
        self.cwl_yaml_button.setEnabled(not locked)
        self.cancel_button.setEnabled(not locked)
        self.deploy_button.setEnabled(not locked)
        self.yaml_editor.setEnabled(not locked)
        self.cwl_url_input.setEnabled(not locked)
