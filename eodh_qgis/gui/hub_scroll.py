"""Consistent pixel scrolling for lists, expanded cards and their controls."""

from qgis.PyQt import QtCore, QtWidgets


class SmoothScroll(QtCore.QObject):
    def __init__(self, area):
        super().__init__(area)
        self.area = area
        self.animations = {}
        if isinstance(area, QtWidgets.QAbstractItemView):
            area.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
            area.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        for bar in (area.verticalScrollBar(), area.horizontalScrollBar()):
            # Qt otherwise derives this from row height, including expanded assets.
            bar.setSingleStep(16)
            animation = QtCore.QPropertyAnimation(bar, b"value", self)
            animation.setDuration(140)
            animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
            bar.sliderPressed.connect(animation.stop)
            bar.actionTriggered.connect(animation.stop)
            self.animations[bar] = animation
        area.viewport().installEventFilter(self)

    def watch(self, widget):
        """Route wheel input over inline labels, checkboxes and selectors too."""
        widget.installEventFilter(self)
        for child in widget.findChildren(QtWidgets.QWidget):
            if isinstance(child, QtWidgets.QAbstractScrollArea):
                continue
            parent = child.parentWidget()
            while parent is not None and parent is not widget:
                if isinstance(parent, (QtWidgets.QAbstractScrollArea, QtWidgets.QComboBox)):
                    break
                parent = parent.parentWidget()
            else:
                child.installEventFilter(self)

    def stop(self):
        for animation in self.animations.values():
            animation.stop()

    def eventFilter(self, obj, event):
        if event.type() != QtCore.QEvent.Type.Wheel:
            return False
        horizontal = bool(event.angleDelta().x() or event.pixelDelta().x()) or bool(
            event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier
        )
        vertical = self.area.verticalScrollBar()
        horizontal = horizontal or vertical.maximum() == vertical.minimum()
        bar = self.area.horizontalScrollBar() if horizontal else vertical
        pixels, angle = event.pixelDelta(), event.angleDelta()
        delta = (pixels.x() or pixels.y()) if horizontal else pixels.y()
        animation = self.animations[bar]
        running = animation.state() == QtCore.QAbstractAnimation.State.Running
        start = animation.endValue() if running else bar.value()
        if delta:
            # Trackpads already provide smooth, high-resolution pixel movement.
            animation.stop()
            bar.setValue(bar.value() - delta)
        else:
            delta = (angle.x() or angle.y()) if horizontal else angle.y()
            distance = delta / 120 * bar.singleStep() * QtWidgets.QApplication.wheelScrollLines()
            target = max(bar.minimum(), min(bar.maximum(), round(start - distance)))
            animation.stop()
            animation.setStartValue(bar.value())
            animation.setEndValue(target)
            animation.start()
        event.accept()
        return True


class SmoothScrollArea(QtWidgets.QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scrolling = SmoothScroll(self)

    def setWidget(self, widget):
        super().setWidget(widget)
        self.scrolling.watch(widget)

    def showEvent(self, event):
        # Search forms add their controls after assigning the content widget.
        if self.widget() is not None:
            self.scrolling.watch(self.widget())
        super().showEvent(event)


class ScrollComboBox(QtWidgets.QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scrolling = SmoothScroll(self.view())

    def wheelEvent(self, event):
        # Scrolling over a closed selector should move its containing list,
        # rather than change collection, licence or workspace filters.
        event.ignore()
