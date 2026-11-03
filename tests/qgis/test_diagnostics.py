"""Errors explain themselves in a screenshot, and Debug info collects the rest."""

import re
import socket
import sys
import time
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from qgis.core import Qgis, QgsApplication, QgsProject, QgsRasterLayer, QgsVectorLayer
from qgis.PyQt import QtTest, QtWidgets

from eodh_qgis import diagnostics
from eodh_qgis.api.hub import HubClient, PythonNetwork, asset_type
from eodh_qgis.api.qgis_network import QgisNetwork
from eodh_qgis.main import EodhQgis

METADATA = (Path(__file__).parents[2] / "metadata.txt").read_text(encoding="utf-8")
VERSION = re.search(r"^version=(.+)$", METADATA, re.MULTILINE).group(1)


def wait_for_tasks(dock):
    deadline = time.monotonic() + 30
    while dock.tasks and time.monotonic() < deadline:
        QtTest.QTest.qWait(20)
    assert not dock.tasks, "Background tasks did not finish"
    QgsApplication.taskManager().threadPool().waitForDone()


@pytest.fixture
def local_probes(http_server, monkeypatch):
    http_server.routes[diagnostics.PROBE_PATH] = lambda h: h.reply(200, b'{"type": "Catalog"}')
    monkeypatch.setitem(diagnostics.PROBES, "Python", lambda: diagnostics.probe(PythonNetwork(), http_server.base))
    monkeypatch.setitem(diagnostics.PROBES, "QGIS network", lambda: diagnostics.probe(QgisNetwork(), http_server.base))
    monkeypatch.setitem(
        diagnostics.PROBES, "GDAL (raster streaming)", lambda: diagnostics.probe_gdal(http_server.base)
    )
    for name in ("http_proxy", "HTTP_PROXY"):
        monkeypatch.delenv(name, raising=False)


def test_unexpected_error_shows_type_and_location_and_debug_info_keeps_its_traceback(dock, local_probes):
    client = HubClient("https://hub.test", "geovation", "fake-test-key")
    # A workspace collection without an id, as a malformed service response would send.
    client.request = lambda url: {"collections": [{"links": []}]}
    dock.client = client
    dock.refresh_records()
    wait_for_tasks(dock)
    assert re.fullmatch(r"Unexpected error: KeyError: 'id' at hub\.py:\d+ in records", dock.workspace_error.text())

    dock.show_debug_info()
    wait_for_tasks(dock)
    report = dock.debug_dialog.text.toPlainText()
    assert f"EODH plugin {VERSION} · QGIS {Qgis.version()}" in report
    assert re.search(r"Signed in\s+: yes, workspace geovation at https://hub\.test", report)
    assert re.search(r"Python\s+: HTTP 200 in [\d.]+ s \(direct\)", report)
    assert re.search(r"QGIS network\s+: HTTP 200 in [\d.]+ s \(direct\)", report)
    assert re.search(r"GDAL \(raster streaming\)\s+: reachable", report)
    assert "Loading workspace commercial data...\nUnexpected error: KeyError: 'id'" in report
    assert "Traceback (most recent call last)" in report
    assert "in records" in report
    assert "fake-test-key" not in report
    dock.debug_dialog.copy_button.click()
    assert QtWidgets.QApplication.clipboard().text() == report


def test_login_page_shows_versions_and_opens_debug_info(dock_factory, local_probes):
    dock = dock_factory()
    assert dock.login.versions.text().startswith(f"EODH plugin {VERSION} · QGIS {Qgis.version()}")
    dock.login.debug.linkActivated.emit("debug-info")
    assert dock.debug_dialog.isVisible()
    wait_for_tasks(dock)
    assert re.search(r"Signed in\s+: no", dock.debug_dialog.text.toPlainText())


def test_uncaught_plugin_errors_are_kept_until_debug_info_is_opened(iface, monkeypatch):
    shown = []
    monkeypatch.setattr(sys, "excepthook", lambda *exc: shown.append(exc))
    plugin = EodhQgis(iface)
    plugin.initGui()
    try:
        try:
            asset_type(None)
        except AttributeError:
            sys.excepthook(*sys.exc_info())
    finally:
        plugin.unload()
    assert len(shown) == 1, "QGIS must still show the error"
    latest = diagnostics.recent_errors()[0]
    assert latest["context"] == "Unhandled error"
    assert re.fullmatch(r"Unexpected error: AttributeError: .+ at hub\.py:\d+ in asset_type", latest["message"])
    assert "asset_type" in latest["traceback"]
    sys.excepthook(*shown[0])
    assert len(shown) == 2, "Unloading restores the previous hook"


def test_quick_view_failure_dialog_names_the_reason_and_versions(dock, scene, monkeypatch):
    monkeypatch.setattr(
        "eodh_qgis.gui.hub_dock.quick_view", lambda item, base: ("https://tiles.test/{z}/{x}/{y}.png", "True colour")
    )
    # The tile provider refuses the source, as a broken or blocked tile service would.
    monkeypatch.setattr(
        "eodh_qgis.gui.hub_dock.QgsRasterLayer", lambda uri, name, provider: QgsRasterLayer("/missing.tif", name)
    )
    dock.client = SimpleNamespace(base="https://hub.test")
    card = SimpleNamespace(item=scene, loading=False, update_enabled=lambda: None)
    with patch.object(QtWidgets.QMessageBox, "warning") as warning:
        dock.load_quick_view(card)
    title, text = warning.call_args.args[1:]
    assert title == "EODH - Quick View Error"
    assert re.match(r"Failed to open Quick view for this item\.\n\nQuick view could not be opened: .*\S", text)
    assert "QGIS gave no reason" not in text
    assert text.endswith(diagnostics.environment_line())
    assert dock.status.text() == "Asset load failed"
    assert diagnostics.recent_errors()[0]["context"] == "Opening Quick view"


def test_debug_info_reports_failed_checks_replaced_openers_and_streamed_layers(dock, monkeypatch):
    with socket.socket() as closed:
        closed.bind(("127.0.0.1", 0))
        base = f"http://127.0.0.1:{closed.getsockname()[1]}"
    for name in ("http_proxy", "HTTP_PROXY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setitem(diagnostics.PROBES, "Python", lambda: diagnostics.probe(PythonNetwork(), base))
    monkeypatch.setitem(diagnostics.PROBES, "QGIS network", lambda: diagnostics.probe(QgisNetwork(), base))
    monkeypatch.setitem(diagnostics.PROBES, "GDAL (raster streaming)", lambda: diagnostics.probe_gdal(base))
    # What QGIS's MetaSearch plugin does at startup when a QGIS proxy is set.
    proxy = urllib.request.ProxyHandler({"http": "http://user:proxy-secret@proxy.test:8080"})
    monkeypatch.setattr(urllib.request, "_opener", urllib.request.build_opener(proxy))
    layer = QgsVectorLayer("Point?crs=EPSG:4326", "scene_visual", "memory")
    layer.setCustomProperty("eodh/remote_url", "https://data.test/scene/visual.tif?X-Amz-Signature=signed-secret")
    QgsProject.instance().addMapLayer(layer)
    dock.show_debug_info()
    wait_for_tasks(dock)
    report = dock.debug_dialog.text.toPlainText()
    assert re.search(r"Python\s+: failed: Connection refused in [\d.]+ s \(direct\)", report)
    assert re.search(r"QGIS network\s+: failed: Connection refused \(\w+\) in [\d.]+ s \(direct\)", report)
    assert re.search(r"GDAL \(raster streaming\)\s+: failed: ", report)
    assert "replaced by another plugin (proxies: [{'http': 'http://[credentials]@proxy.test:8080'}])" in report
    assert "scene_visual (streamed from data.test/scene/visual.tif, valid)" in report
    assert "secret" not in report


def test_asset_load_failure_dialog_names_the_error_and_versions(dock, scene, pending, monkeypatch):
    monkeypatch.setattr(
        "eodh_qgis.raster_loader.load_asset", Mock(side_effect=RuntimeError("GDAL could not decode tile 3"))
    )
    dock.client = Mock(base="https://example.test")
    dock.display_page({"features": [scene]})
    card = dock.result_cards[0]
    card.assets.boxes[0][0].setChecked(True)
    task = Mock()
    task.isCanceled.return_value = False
    with patch.object(QtWidgets.QMessageBox, "warning") as warning:
        dock.load_card(card)
        work, done, _ = pending.pop()
        done(work(task))
    title, text = warning.call_args.args[1:]
    assert title == "EODH — Asset Load Error"
    assert re.fullmatch(
        r"Failed to load asset 'cog' \(GeoTIFF\)\.\n\nError: Unexpected error: RuntimeError: GDAL could not "
        r"decode tile 3 at hub_dock\.py:\d+ in work\n\n" + re.escape(diagnostics.environment_line()),
        text,
    )
    assert dock.status.text() == "Asset load failed"
    assert diagnostics.recent_errors()[0]["context"] == "Loading asset 'cog'"
    dock.client = None
