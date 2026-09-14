"""Inline result/workspace cards and the ArcGIS thumbnail timeline."""

from qgis.PyQt import QtCore, QtGui, QtWidgets

from eodh_qgis.api.hub import COMPLETED, asset_type, href, property_value, record_status
from eodh_qgis.api.presentation import default_assets, display_date, file_type, metadata, parsed_date, quick_view

from .hub_widgets import CommercialPanel, button, label


def text_label(text, size=10, bold=False, color=None):
    widget = label(str(text))
    widget.setStyleSheet(f"font-size:{size}px;" + (f"color:{color};" if color else ""))
    if bold:
        font = widget.font()
        font.setWeight(QtGui.QFont.Weight.DemiBold)
        widget.setFont(font)
    return widget


def hyperlink(text, url, size=10):
    widget = text_label("", size)
    widget.setTextFormat(QtCore.Qt.TextFormat.RichText)
    widget.setText(f'<a href="{url}" style="color:#006a8a;text-decoration:none;">{text}</a>')
    widget.setOpenExternalLinks(True)
    return widget


def busy_bar(parent=None, height=3):
    widget = QtWidgets.QProgressBar(parent)
    widget.setRange(0, 0)
    widget.setFixedHeight(height)
    widget.setTextVisible(False)
    widget.hide()
    return widget


class ElideLabel(QtWidgets.QLabel):
    clicked = QtCore.pyqtSignal()

    def __init__(self, text, size=10, bold=False, color=None):
        super().__init__()
        self.value = str(text or "")
        self.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self.setToolTip(self.value)
        self.setMinimumWidth(0)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred)
        self.setStyleSheet(f"font-size:{size}px;" + (f"color:{color};" if color else ""))
        if bold:
            font = self.font()
            font.setWeight(QtGui.QFont.Weight.DemiBold)
            self.setFont(font)
        self.setText(self.value)

    def resizeEvent(self, event):
        self.setText(self.fontMetrics().elidedText(self.value, QtCore.Qt.TextElideMode.ElideRight, self.width()))
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class CardList(QtWidgets.QListWidget):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setStyleSheet("QListWidget {background:transparent;border:0;} QListWidget::item {padding:0;border:0;}")

    def add_card(self, card):
        row = QtWidgets.QListWidgetItem()
        self.addItem(row)
        self.setItemWidget(row, card)
        card.changed.connect(lambda: self.fit_cards())
        self.fit_cards()

    def fit_cards(self):
        width = max(150, self.viewport().width())
        for index in range(self.count()):
            row = self.item(index)
            card = self.itemWidget(row)
            if card:
                card.setFixedWidth(width)
                height = card.layout().heightForWidth(width)
                row.setSizeHint(QtCore.QSize(width, max(height, card.minimumSizeHint().height())))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_cards()


class WrapLayout(QtWidgets.QLayout):
    """Keep each metadata field intact while wrapping rows like WPF WrapPanel."""

    def __init__(self, parent):
        super().__init__(parent)
        self.entries = []
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self.entries.append(item)

    def count(self):
        return len(self.entries)

    def itemAt(self, index):
        return self.entries[index] if 0 <= index < len(self.entries) else None

    def takeAt(self, index):
        return self.entries.pop(index) if 0 <= index < len(self.entries) else None

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.arrange(QtCore.QRect(0, 0, width, 0), False)

    def minimumSize(self):
        return QtCore.QSize(0, max((item.sizeHint().height() for item in self.entries), default=0))

    def sizeHint(self):
        return self.minimumSize()

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.arrange(rect, True)

    def arrange(self, rect, apply):
        x, y, row_height = rect.x(), rect.y(), 0
        for item in self.entries:
            size = item.sizeHint()
            width = min(size.width(), rect.width())
            if x > rect.x() and x + width > rect.right() + 1:
                x, y, row_height = rect.x(), y + row_height, 0
            if apply:
                item.setGeometry(QtCore.QRect(x, y, width, size.height()))
            x += width + 8
            row_height = max(row_height, size.height())
        return y + row_height - rect.y()


def metadata_row(fields, size=10, color=None):
    widget = QtWidgets.QWidget()
    layout = WrapLayout(widget)
    for value in fields:
        caption = text_label(value, size, color=color)
        caption.setWordWrap(False)
        layout.addWidget(caption)
    return widget


class AssetChoices(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal()

    def __init__(self, item, workspace=False):
        super().__init__()
        self.boxes = []
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        defaults = {key.lower() for key in default_assets(item.get("collection"))}
        for key, asset in (item.get("assets") or {}).items():
            row = QtWidgets.QHBoxLayout()
            row.setContentsMargins(1, 2, 0, 2)
            box = QtWidgets.QCheckBox()
            box.setToolTip(key)
            box.setEnabled(bool(asset_type(asset)))
            box.setChecked(bool(asset_type(asset)) and (workspace or key.lower() in defaults))
            box.toggled.connect(self.changed)
            row.addWidget(box)
            display = asset.get("title") or key
            caption = ElideLabel(
                f"{display} ({file_type(asset)})" if workspace else display, color=None if box.isEnabled() else "#999"
            )
            caption.clicked.connect(box.click)
            row.addWidget(caption, 1)
            if not workspace:
                badge = text_label(file_type(asset), 9, color="#407040" if box.isEnabled() else "#906060")
                badge.setStyleSheet(
                    badge.styleSheet()
                    + f"background:{'#e0f0e0' if box.isEnabled() else '#f0e0e0'};border-radius:2px;padding:1px 4px;"
                )
                row.addWidget(badge)
            layout.addLayout(row)
            self.boxes.append((box, key, asset))

    def selected(self):
        return [(key, asset) for box, key, asset in self.boxes if box.isChecked() and box.isEnabled()]


class ResultCard(QtWidgets.QFrame):
    changed = QtCore.pyqtSignal()
    selected = QtCore.pyqtSignal()

    def __init__(self, dock, item, licence=None):
        super().__init__()
        self.setObjectName("resultCard")
        self.dock, self.item = dock, item
        self.loading = False
        self.layout_box = QtWidgets.QVBoxLayout(self)
        self.layout_box.setContentsMargins(11, 6, 8, 6)
        self.layout_box.setSpacing(0)
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(12)
        self.thumbnail = QtWidgets.QLabel()
        self.thumbnail.setFixedSize(56, 56)
        self.thumbnail.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setStyleSheet("background:rgba(128,128,128,32);border-radius:3px;")
        row.addWidget(self.thumbnail, 0, QtCore.Qt.AlignmentFlag.AlignTop)
        info = QtWidgets.QVBoxLayout()
        info.setSpacing(1)
        info.addWidget(ElideLabel(item.get("id"), 11, True))
        info.addWidget(ElideLabel(item.get("collection"), 10, color="#666"))
        self.metadata = metadata_row(metadata(item, dock.bbox, licence))
        info.addWidget(self.metadata)
        assets = item.get("assets") or {}
        loadable = sum(bool(asset_type(a)) for a in assets.values())
        self.expand = button(f"{loadable} loadable / {len(assets)} total assets", self.toggle_assets)
        self.expand.setObjectName("assetLink")
        info.addWidget(self.expand, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        self.asset_panel = QtWidgets.QWidget()
        asset_layout = QtWidgets.QVBoxLayout(self.asset_panel)
        asset_layout.setContentsMargins(0, 3, 0, 0)
        asset_layout.setSpacing(4)
        self.assets = AssetChoices(item)
        self.has_defaults = bool(self.assets.selected())
        asset_layout.addWidget(self.assets)
        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(6)
        self.quick = button("Quick view", lambda: dock.load_quick_view(self))
        self.quick.setToolTip("Add the default rendered preview for this item to the active map")
        self.quick.setVisible(quick_view(item) is not None)
        actions.addWidget(self.quick)
        self.load_button = button("Load Selected Assets", lambda: dock.load_card(self))
        actions.addWidget(self.load_button)
        actions.addStretch()
        asset_layout.addLayout(actions)
        self.assets.changed.connect(self.update_enabled)
        self.asset_panel.hide()
        info.addWidget(self.asset_panel)
        self.progress = busy_bar(height=2)
        info.addWidget(self.progress)
        row.addLayout(info, 1)
        self.layout_box.addLayout(row)
        self.commercial = None
        if "/catalogs/commercial/" in (href(item, "self") or "").lower():
            self.layout_box.addSpacing(6)
            self.commercial = CommercialPanel(dock)
            self.commercial.set_item(item)
            self.commercial.changed.connect(self.changed)
            self.layout_box.addWidget(self.commercial)
        self.set_selected(False)
        self.update_enabled()

    def set_selected(self, selected):
        self.setStyleSheet(
            "QFrame#resultCard {border:0;border-left:3px solid "
            + ("#3078c0" if selected else "transparent")
            + ";border-bottom:1px solid gray;background:"
            + ("#c7e8f6" if selected else "transparent")
            + ";}"
        )

    def set_thumbnail(self, pixmap):
        self.thumbnail.setPixmap(
            pixmap.scaled(
                56,
                56,
                QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
        )

    def toggle_assets(self):
        self.asset_panel.setVisible(self.asset_panel.isHidden())
        self.changed.emit()

    def update_enabled(self):
        self.load_button.setEnabled(bool(self.assets.selected()) and not self.loading)
        self.quick.setEnabled(not self.loading)
        self.progress.setVisible(self.loading)
        self.changed.emit()

    def mousePressEvent(self, event):
        self.selected.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.has_defaults:
            self.dock.load_card(self)
        elif self.asset_panel.isHidden():
            self.toggle_assets()
        super().mouseDoubleClickEvent(event)


class WorkspaceCard(QtWidgets.QFrame):
    changed = QtCore.pyqtSignal()

    def __init__(self, dock, item):
        super().__init__()
        self.dock, self.item, self.loading = dock, item, False
        self.setObjectName("workspaceCard")
        self.setStyleSheet("QFrame#workspaceCard {background:white;border:0;border-bottom:1px solid gray;}")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)
        row = QtWidgets.QHBoxLayout()
        title = QtWidgets.QVBoxLayout()
        title.setSpacing(0)
        title.addWidget(
            ElideLabel(
                f"{item['_provider']} — {item.get('_collection_label') or item.get('collection') or ''}", 11, True
            )
        )
        title.addWidget(ElideLabel(item.get("id"), 10, color="#666"))
        row.addLayout(title, 1)
        status = text_label(
            property_value(item, "order:status", "order_status", "order:state", "status", default="unknown"), 10, True
        )
        status.setStyleSheet(status.styleSheet() + "background:rgba(48,128,192,32);border-radius:3px;padding:2px 5px;")
        row.addWidget(status, 0, QtCore.Qt.AlignmentFlag.AlignTop)
        layout.addLayout(row)
        message = property_value(
            item, "order:message", "order_message", "failure_message", "message", "detail", default=""
        )
        if message:
            layout.addWidget(text_label(message, 10, color="#b8860b"))
        dates = (
            "Order: " + property_value(item, "order:id", "order_id", "orderId", default=""),
            "Created: "
            + display_date(
                property_value(item, "created", "order:date", "order_date", "ordered", "ordered_at", default="")
            ),
            "Updated: " + display_date(property_value(item, "updated", default="")),
        )
        layout.addSpacing(12 if not message else 2)
        layout.addWidget(metadata_row(dates, 9, color="#777"))
        layout.addSpacing(5)
        self.can_load = record_status(item) in COMPLETED and any(
            asset_type(a) for a in (item.get("assets") or {}).values()
        )
        self.expand = QtWidgets.QToolButton()
        self.expand.setText("Available loadable files")
        self.expand.setCheckable(True)
        self.expand.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.expand.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        self.expand.setStyleSheet("border:0;background:transparent;padding:3px 0;")
        self.expand.setVisible(self.can_load)
        layout.addWidget(self.expand, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        self.asset_panel = QtWidgets.QWidget()
        inner = QtWidgets.QVBoxLayout(self.asset_panel)
        inner.setContentsMargins(18, 3, 0, 0)
        inner.setSpacing(4)
        self.assets = AssetChoices(item, workspace=True)
        inner.addWidget(self.assets)
        actions = QtWidgets.QHBoxLayout()
        self.load_button = button("Load into map", lambda: dock.load_card(self))
        actions.addWidget(self.load_button)
        self.progress = busy_bar(height=2)
        self.progress.setFixedWidth(60)
        actions.addWidget(self.progress)
        actions.addStretch()
        inner.addLayout(actions)
        layout.addWidget(self.asset_panel)
        self.asset_panel.hide()
        self.expand.toggled.connect(self.toggle)
        self.assets.changed.connect(self.update_enabled)
        self.update_enabled()

    def toggle(self, expanded):
        self.expand.setArrowType(QtCore.Qt.ArrowType.DownArrow if expanded else QtCore.Qt.ArrowType.RightArrow)
        self.asset_panel.setVisible(expanded)
        self.changed.emit()

    def update_enabled(self):
        self.load_button.setEnabled(self.can_load and bool(self.assets.selected()) and not self.loading)
        self.progress.setVisible(self.loading)
        self.changed.emit()


class Timeline(QtWidgets.QWidget):
    selected = QtCore.pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setFixedHeight(92)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)
        self.previous = button("<", lambda: self.step(-1))
        self.next = button(">", lambda: self.step(1))
        for control in (self.previous, self.next):
            control.setFixedWidth(24)
            control.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Expanding)
        layout.addWidget(self.previous)
        self.strip = QtWidgets.QScrollArea()
        self.strip.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.strip.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.strip.setStyleSheet("QScrollArea {background:transparent;}")
        layout.addWidget(self.strip, 1)
        layout.addWidget(self.next)
        self.index, self.order, self.images = -1, [], {}
        self.set_items([])

    def set_items(self, items):
        old = self.strip.takeWidget()
        if old:
            old.deleteLater()
        content = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(content)
        row.setContentsMargins(2, 0, 2, 0)
        row.setSpacing(4)
        self.images = {}
        dates = [
            (i, date.timestamp())
            for i, item in enumerate(items)
            if (date := parsed_date((item.get("properties") or {}).get("datetime"))) is not None
        ]
        self.order = [i for i, date in sorted(dates, key=lambda pair: pair[1])]
        for index in self.order:
            entry = QtWidgets.QToolButton()
            entry.setFixedSize(64, 64)
            entry.setIconSize(QtCore.QSize(56, 42))
            entry.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            entry.setText(display_date(items[index]["properties"]["datetime"], "%m/%d"))
            entry.setToolTip(str(items[index].get("id", "")))
            entry.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            placeholder = QtGui.QPixmap(56, 42)
            placeholder.fill(QtGui.QColor(128, 128, 128, 32))
            entry.setIcon(QtGui.QIcon(placeholder))
            entry.clicked.connect(lambda checked=False, i=index: self.selected.emit(i))
            row.addWidget(entry)
            self.images[index] = entry
        content.setFixedSize(max(4, 68 * len(self.order)), 64)
        self.strip.setWidget(content)
        self.select(-1)

    def select(self, index):
        self.index = index
        position = self.order.index(index) if index in self.order else -1
        for item_index, entry in self.images.items():
            entry.setStyleSheet(
                "QToolButton {font-size:9px;border-radius:3px;padding:0;border:2px solid "
                + (
                    "#0078d7;background:rgba(0,120,215,40);"
                    if item_index == index
                    else "transparent;background:transparent;"
                )
                + "}"
            )
        if position >= 0:
            QtCore.QTimer.singleShot(0, self.center_selection)
        self.previous.setEnabled(position > 0)
        self.next.setEnabled(bool(self.order) and position < len(self.order) - 1)

    def center_selection(self):
        if self.index in self.images:
            entry = self.images[self.index]
            self.strip.horizontalScrollBar().setValue(entry.x() - self.strip.viewport().width() // 2 + 32)

    def choose(self, position):
        if 0 <= position < len(self.order):
            self.selected.emit(self.order[position])

    def step(self, direction):
        position = self.order.index(self.index) if self.index in self.order else -1
        self.choose(position + direction)

    def set_thumbnail(self, index, pixmap):
        if index in self.images:
            scaled = pixmap.scaled(
                56,
                42,
                QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            self.images[index].setIcon(
                QtGui.QIcon(scaled.copy((scaled.width() - 56) // 2, (scaled.height() - 42) // 2, 56, 42))
            )
