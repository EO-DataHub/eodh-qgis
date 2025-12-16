"""Background layer loading task for QGIS.

Simple wrapper around create_layers_for_asset() that runs in background thread.
"""

from __future__ import annotations

from qgis.core import Qgis, QgsMessageLog, QgsRasterLayer, QgsTask

from eodh_qgis.definitions.constants import PLUGIN_NAME
from eodh_qgis.layer_utils import create_layers_for_asset


class LayerLoaderTask(QgsTask):
    """Background task that wraps create_layers_for_asset().

    Usage:
        task = LayerLoaderTask(item, asset_key, asset, selected_variables)
        task.taskCompleted.connect(partial(on_complete, task))
        QgsApplication.taskManager().addTask(task)

    After completion, access task.layers for the loaded layers.
    """

    def __init__(
        self,
        item,
        asset_key: str,
        asset,
        selected_variables: list[str] | None = None,
    ):
        super().__init__(f"Loading {item.id}/{asset_key}")
        self.item = item
        self.asset_key = asset_key
        self.asset = asset
        self.selected_variables = selected_variables
        # Results - accessed after task completes
        self.layers: list[QgsRasterLayer] = []
        self.error: str | None = None

    def run(self) -> bool:
        """Execute layer loading in background thread."""
        try:
            QgsMessageLog.logMessage(
                f"[Task] Starting background load for {self.item.id}/{self.asset_key}",
                PLUGIN_NAME,
                level=Qgis.Info,
            )

            # Progress callback - scale download to 0-80%, leave 20% for layer creation
            def on_download_progress(percent: int):
                self.setProgress(percent * 0.8)

            # Reuse existing function - all the download/layer logic is there
            self.layers = create_layers_for_asset(
                self.item,
                self.asset_key,
                self.asset,
                self.selected_variables,
                progress_callback=on_download_progress,
            )

            self.setProgress(100)  # Done

            if not self.layers:
                self.error = f"No valid layers created for {self.asset_key}"
                return False

            return True

        except Exception as e:
            self.error = str(e)
            QgsMessageLog.logMessage(
                f"[Task] Error: {e}",
                PLUGIN_NAME,
                level=Qgis.Warning,
            )
            return False

    def finished(self, result: bool):
        """Called on main thread when task completes."""
        if result and self.layers:
            # Clone layers for thread safety
            self.layers = [layer.clone() for layer in self.layers]
            QgsMessageLog.logMessage(
                f"[Task] Finished loading {len(self.layers)} layer(s)",
                PLUGIN_NAME,
                level=Qgis.Info,
            )
        elif self.error:
            QgsMessageLog.logMessage(
                f"[Task] Failed: {self.error}",
                PLUGIN_NAME,
                level=Qgis.Warning,
            )
