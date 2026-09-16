"""Exercise the real plugin entry point, dock lifecycle and cleanup."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qgis.core import QgsApplication, QgsProject, QgsVectorLayer
from qgis.gui import QgsMapCanvas
from qgis.PyQt import QtCore, QtWidgets
from qgis_test_support import finish

from eodh_qgis import classFactory
from eodh_qgis.gui.hub_dock import HubDock

app = QgsApplication([], False)
app.initQgis()
window = QtWidgets.QMainWindow()
canvas = QgsMapCanvas(window)
window.setCentralWidget(canvas)
iface = Mock()
iface.mainWindow.return_value = window
iface.mapCanvas.return_value = canvas
iface.addDockWidget.side_effect = window.addDockWidget
iface.removeDockWidget.side_effect = window.removeDockWidget
user_layer = QgsVectorLayer("Point?crs=EPSG:4326", "Existing project layer", "memory")
QgsProject.instance().addMapLayer(user_layer)
window.show()
with patch.object(HubDock, "load_credentials", lambda self: None):
    plugin = classFactory(iface)
    plugin.initGui()
    assert len(plugin.actions) == 1
    assert not plugin.actions[0].icon().isNull()
    iface.addToolBarIcon.assert_called_once_with(plugin.actions[0])
    plugin.actions[0].trigger()
    app.processEvents()
    dock = plugin.dlg
    assert isinstance(dock, HubDock)
    assert [dock.tabs.tabText(i) for i in range(dock.tabs.count())] == ["Search", "Results", "Workspace"]
    assert dock.stack.currentWidget() == dock.login_scroll
    assert not dock.isHidden()
    plugin.run()
    assert plugin.dlg is dock
    iface.addDockWidget.assert_called_once_with(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)
    dock.set_bbox([0, 0, 1, 1])
    dock.draw()
    assert canvas.mapTool() is dock.draw_tool
    task = Mock()
    dock.tasks.append(task)
    epoch = dock.epoch
    plugin.unload()
    task.cancel.assert_called_once()
    assert dock.epoch > epoch
    assert dock.client is None
    assert dock.isHidden()
    assert not dock.overlays.bands
    assert canvas.mapTool() is not dock.draw_tool
    assert QgsProject.instance().mapLayer(user_layer.id()) is user_layer
    iface.removeDockWidget.assert_called_once_with(dock)
    iface.removeToolBarIcon.assert_called_once_with(plugin.actions[0])
    iface.removePluginWebMenu.assert_called_once_with(plugin.menu, plugin.actions[0])
print(
    "PASS plugin entry point, one dock, current screens, unload cancellation/map cleanup and existing project layers"
)
finish()
