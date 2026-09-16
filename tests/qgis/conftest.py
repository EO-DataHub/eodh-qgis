"""Real QGIS/Qt fixtures. No application or widgets are created during collection."""

import gc
import os
from copy import deepcopy
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from osgeo import gdal
from qgis.core import QgsApplication, QgsProject
from qgis.gui import QgsMapCanvas
from qgis.PyQt import QtCore, QtWidgets

from eodh_qgis.gui.hub_dock import HubDock
from eodh_qgis.raster_loader import clear_stream_credentials


@pytest.fixture(scope="session")
def qgis_app(tmp_path_factory):
    use_exceptions = gdal.GetUseExceptions()
    gdal.DontUseExceptions()
    profile = tmp_path_factory.mktemp("qgis-profile")
    app = QgsApplication([], False, str(profile))
    app.initQgis()
    yield app
    QgsProject.instance().clear()
    app.processEvents()
    gc.collect()
    app.exitQgis()
    if use_exceptions:
        gdal.UseExceptions()


@pytest.fixture(autouse=True)
def clean_project(qgis_app):
    QgsProject.instance().clear()
    yield
    QgsProject.instance().clear()
    clear_stream_credentials()
    qgis_app.processEvents()


@pytest.fixture
def iface(qgis_app):
    window = QtWidgets.QMainWindow()
    canvas = QgsMapCanvas(window)
    window.setCentralWidget(canvas)
    window.resize(900, 850)
    interface = Mock()
    interface.mainWindow.return_value = window
    interface.mapCanvas.return_value = canvas
    interface.addDockWidget.side_effect = window.addDockWidget
    interface.removeDockWidget.side_effect = window.removeDockWidget
    window.show()
    yield interface
    canvas.stopRendering()
    window.close()
    window.deleteLater()
    qgis_app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    qgis_app.processEvents()


@pytest.fixture
def dock_factory(iface, qgis_app):
    docks = []

    def create(*, restore=False):
        if restore:
            widget = HubDock(iface)
        else:
            with patch.object(HubDock, "load_credentials", lambda self: None):
                widget = HubDock(iface)
        iface.mainWindow().addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, widget)
        docks.append(widget)
        widget.show()
        qgis_app.processEvents()
        return widget

    yield create
    for widget in reversed(docks):
        widget.shutdown()
        widget.deleteLater()
    qgis_app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)


@pytest.fixture
def dock(dock_factory, qgis_app):
    widget = dock_factory()
    widget.stack.setCurrentWidget(widget.tabs)
    qgis_app.processEvents()
    return widget


@pytest.fixture
def pending(dock, monkeypatch):
    calls = []
    monkeypatch.setattr(
        dock, "submit", lambda title, work, done, failed=None, **kwargs: calls.append((work, done, failed))
    )
    return calls


@pytest.fixture
def scene():
    return {
        "id": "old",
        "collection": "sentinel2_ard",
        "bbox": [0, 0, 1, 1],
        "properties": {"datetime": "2026-01-01T00:00:00Z"},
        "links": [{"rel": "self", "href": "https://example.test/items/old"}],
        "assets": {
            "cog": {"href": "https://example.test/data.tif", "type": "image/tiff"},
            "thumbnail": {"href": "https://example.test/thumb.png", "type": "image/png"},
        },
    }


@pytest.fixture
def commercial(scene):
    item = deepcopy(scene)
    item.update(
        collection="airbus-optical",
        links=[{"rel": "self", "href": "https://eodatahub.org.uk/catalogs/commercial/catalogs/airbus/items/one"}],
    )
    return item


@pytest.fixture
def collection_entry():
    return {
        "label": "Sentinel 2 ARD",
        "search": "https://example.test/search",
        "collection": {
            "id": "sentinel2_ard",
            "extent": {
                "spatial": {"bbox": [[0, 0, 2, 2]]},
                "temporal": {"interval": [["2015-07-08T00:00:00Z", None]]},
            },
        },
    }
