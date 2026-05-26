from qgis.core import Qgis, QgsGeometry, QgsMessageLog, QgsWkbTypes
from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor


class PolygonCaptureTool(QgsMapToolEmitPoint):
    """Map tool for drawing a polygon on the canvas."""

    polygon_captured = pyqtSignal(object)  # Emits QgsGeometry

    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self.rubber_band = QgsRubberBand(canvas, QgsWkbTypes.GeometryType.PolygonGeometry)
        self.rubber_band.setColor(QColor(255, 0, 0, 100))
        self.rubber_band.setWidth(2)
        self.points = []
        QgsMessageLog.logMessage("PolygonCaptureTool initialized", "EODH", level=Qgis.MessageLevel.Info)

    def canvasPressEvent(self, event):
        """Handle mouse click - left-click adds point, right-click finishes polygon."""
        if event.button() == Qt.MouseButton.LeftButton:
            QgsMessageLog.logMessage("canvasPressEvent called (left-click)", "EODH", level=Qgis.MessageLevel.Info)
            point = self.toMapCoordinates(event.pos())
            self.points.append(point)
            QgsMessageLog.logMessage(
                f"Point added: {point}, total points: {len(self.points)}",
                "EODH",
                level=Qgis.MessageLevel.Info,
            )
            self._update_rubber_band()
        elif event.button() == Qt.MouseButton.RightButton:
            QgsMessageLog.logMessage(
                f"canvasPressEvent called (right-click), points: {len(self.points)}",
                "EODH",
                level=Qgis.MessageLevel.Info,
            )
            if len(self.points) >= 3:
                geometry = QgsGeometry.fromPolygonXY([self.points])
                QgsMessageLog.logMessage("Emitting polygon_captured signal", "EODH", level=Qgis.MessageLevel.Info)
                self.polygon_captured.emit(geometry)
            self.points = []

    def _update_rubber_band(self):
        """Update the visual rubber band as points are added."""
        if self.rubber_band is None:
            return
        self.rubber_band.reset(QgsWkbTypes.GeometryType.PolygonGeometry)
        for point in self.points:
            self.rubber_band.addPoint(point)

    def clear(self):
        """Clear the drawn polygon from the canvas without destroying the tool."""
        self.points = []
        if self.rubber_band is not None:
            self.rubber_band.reset(QgsWkbTypes.GeometryType.PolygonGeometry)
            self.rubber_band.hide()

    def cleanup(self):
        """Fully tear down the rubber band — call when the tool is no longer needed."""
        self.clear()
        if self.rubber_band is not None:
            try:
                scene = self.canvas.scene()
                if scene is not None:
                    scene.removeItem(self.rubber_band)
            except RuntimeError:
                pass
            self.rubber_band = None
