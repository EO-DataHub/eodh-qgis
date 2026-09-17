"""Real background download fallback retains its CRS after worker expiry."""

import shutil
import time
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from osgeo import gdal, osr
from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsMapRendererParallelJob,
    QgsMapSettings,
    QgsProject,
)
from qgis.PyQt import QtCore, QtTest, QtWidgets


@pytest.fixture
def expiring_workers(qgis_app):
    pool = QgsApplication.taskManager().threadPool()
    original = pool.expiryTimeout()
    pool.setExpiryTimeout(0)
    yield
    pool.waitForDone()
    pool.setExpiryTimeout(original)


def test_background_fallback_retains_reprojected_pixels(dock, qgis_app, tmp_path, expiring_workers):
    path = str(tmp_path / "ordinary.tif")
    data = gdal.GetDriverByName("GTiff").Create(path, 2049, 2049, 3, gdal.GDT_Byte)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(32630)
    data.SetProjection(srs.ExportToWkt())
    data.SetGeoTransform([705606, 0.3, 0, 5711064, 0, -0.3])
    rng = np.random.default_rng(5)
    for index in range(1, 4):
        data.GetRasterBand(index).WriteArray(rng.integers(20, 220, (2049, 2049), dtype=np.uint8))
    data = None

    class Client:
        base = "https://example.test"
        workspace = "fixture"
        calls = []

        def request(self, url, probe_range=False, destination=None, progress=None):
            self.calls.append("probe" if probe_range else "download")
            if probe_range:
                return True
            shutil.copyfile(path, destination)
            progress(Path(path).stat().st_size, Path(path).stat().st_size)

    dock.client = Client()
    dock.records = [
        {
            "id": "background-fallback",
            "_provider": "Airbus",
            "properties": {"order:status": "succeeded"},
            "assets": {"primaryAsset_R1C1": {"href": "https://example.test/ordinary.tif", "type": "image/tiff"}},
        }
    ]
    dock.filter_records()
    with (
        patch("eodh_qgis.raster_loader.streaming_source", return_value=path),
        patch.object(QtWidgets.QMessageBox, "warning", side_effect=AssertionError("Loading failed")),
    ):
        dock.load_card(dock.record_cards[0])
        deadline = time.monotonic() + 20
        while dock.tasks and time.monotonic() < deadline:
            QtTest.QTest.qWait(20)
        assert not dock.tasks, "Background loading did not finish"
        QgsApplication.taskManager().threadPool().waitForDone()
    assert dock.client.calls == ["probe", "download"]
    layers = list(QgsProject.instance().mapLayers().values())
    assert len(layers) == 1
    layer = layers[0]
    assert layer.crs().isValid()
    assert layer.crs().toWkt(), "CRS definition was lost crossing from the worker to the GUI thread"
    assert layer.crs().authid() == "EPSG:32630"
    assert layer.thread() == qgis_app.thread()
    assert dock.status.text() == "Asset loaded"
    assert not dock.record_cards[0].loading

    target = QgsCoordinateReferenceSystem("EPSG:3857")
    settings = QgsMapSettings()
    settings.setLayers(layers)
    settings.setDestinationCrs(target)
    settings.setExtent(
        QgsCoordinateTransform(layer.crs(), target, QgsProject.instance()).transformBoundingBox(layer.extent())
    )
    settings.setOutputSize(QtCore.QSize(128, 128))
    job = QgsMapRendererParallelJob(settings)
    job.start()
    job.waitForFinished()
    assert not job.errors(), [error.message for error in job.errors()]
    assert job.renderedImage().pixelColor(64, 64).name() != "#ffffff", "Reprojected raster is blank"
    local_path = Path(layer.source())
    QgsProject.instance().removeAllMapLayers()
    layers = layer = job = settings = None
    local_path.unlink()
