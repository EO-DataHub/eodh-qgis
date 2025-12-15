from qgis.PyQt import QtCore, QtWidgets


class LandingWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        """Constructor."""
        super(LandingWidget, self).__init__(parent)
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

        self.setLayout(layout)
