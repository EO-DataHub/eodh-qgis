"""ArcGIS LoginView layout and orbital artwork, in Qt logical pixels."""

from pathlib import Path
from urllib.parse import quote

from qgis.PyQt import QtCore, QtGui, QtWidgets

from .hub_widgets import label


class LoginPage(QtWidgets.QWidget):
    def __init__(self, connect):
        super().__init__()
        self.setObjectName("eodhLogin")
        self.setStyleSheet(
            '#eodhLogin, #eodhLogin QWidget {font-family:"Segoe UI";font-size:12px;color:#222;}'
            "#eodhLogin QLabel {background:transparent;}"
            "#eodhLogin QLabel#loginTitle {font-size:20px;}"
            "#eodhLogin QLabel#loginSubtitle {color:#5e5e5e;}"
            "#eodhLogin QLabel#loginHint {font-size:11px;color:#626262;}"
            "#eodhLogin QLabel#loginError {color:red;}"
            "#eodhLogin QLineEdit {background:white;border:1px solid #bcbcbc;"
            "border-radius:0;padding:0 4px;min-height:20px;max-height:20px;selection-background-color:#4c72ba;}"
            "#eodhLogin QLineEdit#loginKey {min-height:22px;max-height:22px;}"
            "#eodhLogin QLineEdit:hover {border-color:#929292;}"
            "#eodhLogin QLineEdit:focus {border-color:#007ac2;}"
            "#eodhLogin QPushButton {background:#4c72ba;color:white;border:1px solid #4c72ba;"
            "border-radius:0;padding:7px 8px;}"
            "#eodhLogin QPushButton:hover {background:#3f64ab;border-color:#3f64ab;}"
            "#eodhLogin QPushButton:pressed {background:#355898;border-color:#355898;}"
            "#eodhLogin QPushButton:focus {border:2px solid #24395d;padding:6px 7px;}"
            "#eodhLogin QPushButton:disabled {background:#99aed1;border-color:#99aed1;}"
            "#eodhLogin QProgressBar {border:0;background:transparent;}"
            "#eodhLogin QProgressBar::chunk {background:#4c72ba;}"
        )
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(16, 28, 16, 28)
        outer.setSpacing(0)
        outer.addStretch()
        self.form = QtWidgets.QWidget()
        self.form.setMaximumWidth(350)
        self.form.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Maximum)
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(0)
        row.addStretch()
        row.addWidget(self.form, 1)
        row.addStretch()
        outer.addLayout(row)
        outer.addStretch()
        layout = QtWidgets.QVBoxLayout(self.form)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.logo = QtWidgets.QLabel()
        self.logo.setAccessibleName("Earth Observation Data Hub")
        self.logo.setFixedHeight(81)
        self.logo.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.logo.setPixmap(
            QtGui.QPixmap(str(Path(__file__).parents[1] / "brand" / "eodh-logo-colour.png")).scaled(
                218, 81, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation
            )
        )
        layout.addWidget(self.logo)
        layout.addSpacing(14)
        title = label("Connect your workspace")
        title.setObjectName("loginTitle")
        title_font = QtGui.QFont("Segoe UI")
        title_font.setWeight(QtGui.QFont.Weight.DemiBold)
        title.setFont(title_font)
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(7)
        subtitle = label("Sign in with your EODH workspace credentials to search and access satellite imagery.")
        subtitle.setObjectName("loginSubtitle")
        subtitle.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(24)
        self.workspace = QtWidgets.QLineEdit()
        self.workspace.setFixedHeight(22)
        self.workspace.setAccessibleName("Workspace name")
        workspace_label = label("Workspace name")
        workspace_label.setBuddy(self.workspace)
        layout.addWidget(workspace_label)
        layout.addSpacing(4)
        layout.addWidget(self.workspace)
        layout.addSpacing(12)
        self.key = QtWidgets.QLineEdit()
        self.key.setObjectName("loginKey")
        self.key.setFixedHeight(24)
        self.key.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.key.setAccessibleName("Workspace API key")
        key_label = label("Workspace API key")
        key_label.setBuddy(self.key)
        layout.addWidget(key_label)
        layout.addSpacing(4)
        layout.addWidget(self.key)
        layout.addSpacing(4)
        hint = label("Paste the API Key, not the Token ID.")
        hint.setObjectName("loginHint")
        layout.addWidget(hint)
        layout.addSpacing(5)
        self.documentation = self.link_label("Open the EODH workspace documentation")
        self.documentation.setText(
            self.link_html(
                "https://docs.eodatahub.org.uk/Getting-Started/workspaces/workspace-credentials/",
                "\uf000",
                "Workspace documentation",
            )
        )
        layout.addWidget(self.documentation)
        layout.addSpacing(2)
        self.credentials = self.link_label("Open credentials for this EODH workspace")
        layout.addWidget(self.credentials)
        layout.addSpacing(16)
        self.error = label("")
        self.error.setObjectName("loginError")
        self.error.hide()
        layout.addWidget(self.error)
        self.error_gap = QtWidgets.QWidget()
        self.error_gap.setFixedHeight(12)
        self.error_gap.hide()
        layout.addWidget(self.error_gap)
        self.connect_button = QtWidgets.QPushButton("Connect")
        self.connect_button.clicked.connect(connect)
        self.connect_button.setEnabled(False)
        layout.addWidget(self.connect_button)
        self.progress_gap = QtWidgets.QWidget()
        self.progress_gap.setFixedHeight(8)
        self.progress_gap.hide()
        layout.addWidget(self.progress_gap)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(3)
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)
        self.loading = False
        self.workspace.textChanged.connect(self.workspace_changed)
        self.workspace.returnPressed.connect(connect)
        self.key.returnPressed.connect(connect)
        self.workspace_changed()

    @staticmethod
    def link_html(url, icon, text):
        return (
            f'<a href="{url}" style="color:#006a8a;text-decoration:none;font-size:11px;">'
            f'<span style="font-family:Segoe MDL2 Assets;font-size:12px;">{icon}</span>'
            f"&nbsp;&nbsp;{text}</a>"
        )

    @staticmethod
    def link_label(tooltip):
        widget = QtWidgets.QLabel()
        widget.setTextFormat(QtCore.Qt.TextFormat.RichText)
        widget.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextBrowserInteraction)
        widget.setOpenExternalLinks(True)
        widget.setToolTip(tooltip)
        return widget

    def workspace_changed(self):
        url = "https://eodatahub.org.uk/workspaces/?workspace=" + quote(self.workspace.text().strip(), safe="")
        self.credentials.setText(self.link_html(url, "\ue8d7", "Get workspace credentials"))
        self.connect_button.setEnabled(bool(self.workspace.text().strip()) and not self.loading)

    def set_loading(self, loading):
        self.loading = loading
        self.progress.setVisible(loading)
        self.progress_gap.setVisible(loading)
        self.workspace.setEnabled(not loading)
        self.key.setEnabled(not loading)
        self.workspace_changed()

    def set_error(self, text):
        self.error.setText(text)
        self.error.setVisible(bool(text))
        self.error_gap.setVisible(bool(text))

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor("#f8f8f8"))
        bounds = QtCore.QRectF(self.rect()).adjusted(16, 16, -16, -16)
        painter.setClipRect(bounds)
        scale = max(bounds.width() / 520, bounds.height() / 620)
        painter.translate(bounds.center())
        painter.scale(scale, scale)
        painter.translate(-260, -310)
        # Exact Canvas paths, ellipses and composed opacities from LoginView.xaml.
        for points, color, opacity in (
            ((-80, 210, 80, 10, 310, 18, 610, 170), "#4c72ba", 0.5 * 0.24),
            ((-60, 58, 130, 112, 302, 240, 600, 274), "#bdcfeb", 0.5 * 0.32),
        ):
            path = QtGui.QPainterPath(QtCore.QPointF(*points[:2]))
            path.cubicTo(*points[2:])
            painter.setOpacity(opacity)
            painter.setPen(QtGui.QPen(QtGui.QColor(color), 1))
            painter.drawPath(path)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor("#4c72ba"))
        for x, y, diameter, opacity in ((63, 121, 7, 0.5 * 0.24), (340, 69, 10, 0.5 * 0.18)):
            painter.setOpacity(opacity)
            painter.drawEllipse(QtCore.QRectF(x, y, diameter, diameter))
