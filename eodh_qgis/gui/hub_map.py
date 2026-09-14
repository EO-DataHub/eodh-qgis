"""Temporary canvas overlays; never adds footprint layers to the project."""

import json

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsJsonUtils,
    QgsProject,
    QgsRectangle,
    QgsWkbTypes,
)
from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor

WGS84 = QgsCoordinateReferenceSystem("EPSG:4326")


def geometry(value):
    if not value or value.get("type") not in ("Polygon", "MultiPolygon"):
        return None
    features = QgsJsonUtils.stringToFeatureList(json.dumps({"type": "Feature", "properties": {}, "geometry": value}))
    if not features or features[0].geometry().isEmpty():
        return None
    result = features[0].geometry()
    return result if result.isGeosValid() else None


class RectangleTool(QgsMapToolEmitPoint):
    captured = pyqtSignal(object)

    def __init__(self, canvas):
        super().__init__(canvas)
        self.start = None
        self.band = QgsRubberBand(canvas, QgsWkbTypes.GeometryType.PolygonGeometry)
        self.band.setColor(QColor(76, 114, 186, 70))

    def canvasPressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start = self.toMapCoordinates(event.pos())

    def canvasMoveEvent(self, event):
        if self.start:
            rect = QgsRectangle(self.start, self.toMapCoordinates(event.pos()))
            self.band.setToGeometry(QgsGeometry.fromRect(rect), None)

    def canvasReleaseEvent(self, event):
        if self.start and event.button() == Qt.MouseButton.LeftButton:
            rect = QgsRectangle(self.start, self.toMapCoordinates(event.pos()))
            self.start = None
            self.band.reset(QgsWkbTypes.GeometryType.PolygonGeometry)
            self.captured.emit(rect)

    def deactivate(self):
        self.start = None
        self.band.reset(QgsWkbTypes.GeometryType.PolygonGeometry)
        super().deactivate()


class Overlays:
    def __init__(self, canvas):
        self.canvas = canvas
        self.bands = []
        self.aoi = None

    def clear(self):
        for band in self.bands:
            self.canvas.scene().removeItem(band)
        self.bands = []

    def clear_aoi(self):
        if self.aoi is not None:
            self.canvas.scene().removeItem(self.aoi)
            self.aoi = None

    def band(self, geom, selected=False, aoi=False):
        band = QgsRubberBand(self.canvas, QgsWkbTypes.GeometryType.PolygonGeometry)
        band.setToGeometry(geom, WGS84)
        band.setStrokeColor(QColor("#d88a26" if aoi else "#4c72ba"))
        band.setFillColor(QColor(76, 114, 186, 65 if selected else 18))
        band.setWidth(3 if selected else 1)
        return band

    def footprints(self, items, selected=-1, visible=True):
        self.clear()
        if visible:
            for index, item in enumerate(items):
                geom = geometry(item.get("geometry"))
                if geom:
                    self.bands.append(self.band(geom, index == selected))

    def show_aoi(self, bbox, visible=True):
        self.clear_aoi()
        if bbox and visible:
            self.aoi = self.band(QgsGeometry.fromRect(QgsRectangle(*bbox)), aoi=True)

    def extent_wgs84(self, rect):
        transform = QgsCoordinateTransform(self.canvas.mapSettings().destinationCrs(), WGS84, QgsProject.instance())
        rect = transform.transformBoundingBox(rect)
        return [rect.xMinimum(), rect.yMinimum(), rect.xMaximum(), rect.yMaximum()]

    def zoom(self, item):
        geom = geometry(item.get("geometry"))
        if geom:
            transform = QgsCoordinateTransform(
                WGS84, self.canvas.mapSettings().destinationCrs(), QgsProject.instance()
            )
            rect = transform.transformBoundingBox(geom.boundingBox())
            rect.scale(1.15)
            self.canvas.setExtent(rect)
            self.canvas.refresh()
