"""Result item card widget for displaying a single STAC search result."""

import os
from functools import partial

from qgis.core import QgsNetworkContentFetcherTask
from qgis.PyQt import QtCore, QtGui, QtNetwork, QtWidgets, uic
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices

from eodh_qgis.asset_utils import format_bbox, get_asset_file_type

# Load the UI file
FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/result_item_card.ui")
)


class ResultItemCard(QtWidgets.QWidget, FORM_CLASS):
    """Card widget for displaying a single STAC search result item."""

    # Signal emitted when user wants to load assets
    load_assets_requested = QtCore.pyqtSignal(object)  # emits the STAC item

    # Signal emitted when footprint checkbox is toggled (item, checked)
    footprint_toggled = QtCore.pyqtSignal(object, bool)

    def __init__(self, item, parent_widget, show_collection=True, parent=None):
        """Initialize the card widget.

        Args:
            item: STAC item object from pystac/pyeodh
            parent_widget: SearchWidget reference for accessing helper methods
            show_collection: Whether to show the collection label
            parent: Parent QWidget
        """
        super().__init__(parent)
        self.setupUi(self)

        self.item = item
        self.parent_widget = parent_widget
        self.show_collection = show_collection

        self._initialize_ui()
        self._load_thumbnail()

    def _initialize_ui(self):
        """Populate card with item data."""
        # Item ID as title
        self.item_id_label.setText(str(self.item.id))

        # Collection name
        if self.show_collection:
            collection_name = (
                str(self.item.collection) if self.item.collection else "N/A"
            )
            self.collection_label.setText(collection_name)
        else:
            self.collection_label.setVisible(False)

        # Date
        datetime_str = str(self.item.datetime)[:10] if self.item.datetime else "N/A"
        self.date_label.setText(datetime_str)

        # Bbox
        bbox_str = format_bbox(self.item.bbox)
        self.bbox_label.setText(bbox_str)

        # Assets list with clickable links
        self.assets_label.setTextFormat(QtCore.Qt.RichText)
        self.assets_label.setOpenExternalLinks(False)  # Handle clicks ourselves
        self.assets_label.linkActivated.connect(self._on_asset_link_clicked)
        self.assets_label.setText(self._format_assets_as_html())

        # Connect button
        self.load_assets_btn.clicked.connect(self._on_load_assets_clicked)

        # Connect footprint checkbox
        has_geometry = hasattr(self.item, "geometry") and self.item.geometry is not None
        self.footprint_checkbox.setEnabled(has_geometry)
        if not has_geometry:
            self.footprint_checkbox.setToolTip("This item has no geometry/footprint")
        self.footprint_checkbox.toggled.connect(self._on_footprint_toggled)

    def _format_assets_as_html(self):
        """Format assets as HTML with clickable download links."""
        if not self.item.assets:
            return "Assets: N/A"

        parts = []
        for key, asset in self.item.assets.items():
            file_type = get_asset_file_type(asset)
            href = getattr(asset, "href", None)

            if href:
                # Clickable link - opens in browser for download
                parts.append(f'<a href="{href}">{key}</a> ({file_type})')
            else:
                parts.append(f"{key} ({file_type})")

        return "Assets: " + ", ".join(parts)

    def _on_asset_link_clicked(self, url):
        """Open asset URL in default browser for download."""
        QDesktopServices.openUrl(QUrl(url))

    def _find_thumbnail_url(self):
        """Find thumbnail or overview asset URL.

        Returns:
            str or None: URL of thumbnail/overview asset if found
        """
        if not self.item.assets:
            return None

        # First try to find a thumbnail
        for asset_key, asset in self.item.assets.items():
            roles = getattr(asset, "roles", []) or []
            if "thumbnail" in roles or asset_key == "thumbnail":
                return getattr(asset, "href", None)

        # Fall back to overview
        for asset_key, asset in self.item.assets.items():
            roles = getattr(asset, "roles", []) or []
            if "overview" in roles or asset_key == "overview":
                return getattr(asset, "href", None)

        return None

    def _load_thumbnail(self):
        """Asynchronously load thumbnail image."""
        thumbnail_url = self._find_thumbnail_url()
        if not thumbnail_url:
            self.thumbnail_label.setText("No thumbnail")
            return

        # Create network request
        request = QtNetwork.QNetworkRequest(QtCore.QUrl(thumbnail_url))

        # Use QGIS network content fetcher for async loading
        task = QgsNetworkContentFetcherTask(request)
        handler = partial(self._on_thumbnail_fetched, task)
        task.fetched.connect(handler)
        task.run()

    def _on_thumbnail_fetched(self, task):
        """Handle thumbnail network response.

        Args:
            task: QgsNetworkContentFetcherTask that completed
        """
        reply = task.reply()
        if reply.error() == QtNetwork.QNetworkReply.NoError:
            content = reply.readAll()
            self._set_thumbnail_image(content)
        else:
            self.thumbnail_label.setText("Load failed")

    def _set_thumbnail_image(self, content):
        """Set thumbnail image from network response data.

        Args:
            content: QByteArray with image data
        """
        image = QtGui.QImage.fromData(content)
        if image and not image.isNull():
            pixmap = QtGui.QPixmap.fromImage(image)
            scaled = pixmap.scaled(
                150,
                150,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
            self.thumbnail_label.setPixmap(scaled)
        else:
            self.thumbnail_label.setText("Invalid image")

    def _on_load_assets_clicked(self):
        """Handle load assets button click."""
        self.load_assets_requested.emit(self.item)

    def mouseDoubleClickEvent(self, event):
        """Handle double-click to load assets."""
        self.load_assets_requested.emit(self.item)
        super().mouseDoubleClickEvent(event)

    def _on_footprint_toggled(self, checked):
        """Handle footprint checkbox toggle."""
        self.footprint_toggled.emit(self.item, checked)
