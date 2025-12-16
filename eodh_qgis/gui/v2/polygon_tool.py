from qgis.core import Qgis, QgsGeometry, QgsMessageLog, QgsWkbTypes
from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtGui import QColor


class PolygonCaptureTool(QgsMapToolEmitPoint):
    """Map tool for drawing a polygon on the canvas."""

    polygon_captured = pyqtSignal(object)  # Emits QgsGeometry

    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self.rubber_band = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        self.rubber_band.setColor(QColor(255, 0, 0, 100))
        self.rubber_band.setWidth(2)
        self.points = []
        QgsMessageLog.logMessage("PolygonCaptureTool initialized", "EODH", level=Qgis.Info)

    def canvasPressEvent(self, event):
        """Handle mouse click - add point to polygon."""
        QgsMessageLog.logMessage("canvasPressEvent called", "EODH", level=Qgis.Info)
        point = self.toMapCoordinates(event.pos())
        self.points.append(point)
        QgsMessageLog.logMessage(f"Point added: {point}, total points: {len(self.points)}", "EODH", level=Qgis.Info)
        self._update_rubber_band()

    def canvasDoubleClickEvent(self, event):
        """Handle double-click - finish polygon."""
        QgsMessageLog.logMessage(f"canvasDoubleClickEvent called, points: {len(self.points)}", "EODH", level=Qgis.Info)
        if len(self.points) >= 3:
            geometry = QgsGeometry.fromPolygonXY([self.points])
            QgsMessageLog.logMessage("Emitting polygon_captured signal", "EODH", level=Qgis.Info)
            self.polygon_captured.emit(geometry)
        self.points = []

    def _update_rubber_band(self):
        """Update the visual rubber band as points are added."""
        self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)
        for point in self.points:
            self.rubber_band.addPoint(point)

    def reset(self):
        """Reset the tool state."""
        self.points = []
        self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)
