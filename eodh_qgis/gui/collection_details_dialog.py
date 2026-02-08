"""Collection details dialog for displaying collection metadata."""

import os

from qgis.PyQt import QtWidgets, uic

# Load the UI file
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), "../ui/collection_details_dialog.ui"))


class CollectionDetailsDialog(QtWidgets.QDialog, FORM_CLASS):
    """Dialog for displaying detailed collection metadata."""

    def __init__(self, collection, parent=None):
        """Initialize the dialog.

        Args:
            collection: Collection object from pyeodh
            parent: Parent QWidget
        """
        super().__init__(parent)
        self.setupUi(self)

        self.collection = collection

        # Type hints for UI elements
        self.id_input: QtWidgets.QLineEdit
        self.title_input: QtWidgets.QLineEdit
        self.license_input: QtWidgets.QLineEdit
        self.description_input: QtWidgets.QTextEdit
        self.north_input: QtWidgets.QLineEdit
        self.south_input: QtWidgets.QLineEdit
        self.east_input: QtWidgets.QLineEdit
        self.west_input: QtWidgets.QLineEdit
        self.from_date_input: QtWidgets.QLineEdit
        self.to_date_input: QtWidgets.QLineEdit
        self.keywords_list: QtWidgets.QListWidget
        self.links_table: QtWidgets.QTableWidget

        self._populate_data()

    def _populate_data(self):
        """Fill dialog fields with collection metadata."""
        # Overview tab
        self.id_input.setText(self.collection.id or "N/A")
        self.title_input.setText(self.collection.title or "N/A")
        self.description_input.setText(self.collection.description or "N/A")

        # License
        license_text = getattr(self.collection, "license", None) or "N/A"
        self.license_input.setText(license_text)

        # Set window title
        title = self.collection.title or self.collection.id
        self.setWindowTitle(f"Collection Details - {title}")

        # Extent tab
        self._populate_extent()

        # Keywords tab
        self._populate_keywords()

        # Links tab
        self._populate_links()

    def _populate_extent(self):
        """Populate spatial and temporal extent fields."""
        extent = getattr(self.collection, "extent", None)
        if not extent:
            self.north_input.setText("N/A")
            self.south_input.setText("N/A")
            self.east_input.setText("N/A")
            self.west_input.setText("N/A")
            self.from_date_input.setText("N/A")
            self.to_date_input.setText("N/A")
            return

        # Spatial extent
        spatial = getattr(extent, "spatial", None)
        if spatial and hasattr(spatial, "bboxes") and spatial.bboxes:
            bbox = spatial.bboxes[0]  # Use first bbox
            if len(bbox) >= 4:
                self.west_input.setText(f"{bbox[0]:.4f}")
                self.south_input.setText(f"{bbox[1]:.4f}")
                self.east_input.setText(f"{bbox[2]:.4f}")
                self.north_input.setText(f"{bbox[3]:.4f}")
            else:
                self.north_input.setText("N/A")
                self.south_input.setText("N/A")
                self.east_input.setText("N/A")
                self.west_input.setText("N/A")
        else:
            self.north_input.setText("N/A")
            self.south_input.setText("N/A")
            self.east_input.setText("N/A")
            self.west_input.setText("N/A")

        # Temporal extent
        temporal = getattr(extent, "temporal", None)
        if temporal and hasattr(temporal, "intervals") and temporal.intervals:
            interval = temporal.intervals[0]  # Use first interval
            if len(interval) >= 2:
                from_date = interval[0]
                to_date = interval[1]

                if from_date:
                    if hasattr(from_date, "strftime"):
                        self.from_date_input.setText(from_date.strftime("%Y-%m-%d"))
                    else:
                        self.from_date_input.setText(str(from_date)[:10])
                else:
                    self.from_date_input.setText("Open")

                if to_date:
                    if hasattr(to_date, "strftime"):
                        self.to_date_input.setText(to_date.strftime("%Y-%m-%d"))
                    else:
                        self.to_date_input.setText(str(to_date)[:10])
                else:
                    self.to_date_input.setText("Open")
            else:
                self.from_date_input.setText("N/A")
                self.to_date_input.setText("N/A")
        else:
            self.from_date_input.setText("N/A")
            self.to_date_input.setText("N/A")

    def _populate_keywords(self):
        """Populate keywords list."""
        keywords = getattr(self.collection, "keywords", None)
        if keywords:
            for keyword in keywords:
                self.keywords_list.addItem(str(keyword))
        else:
            self.keywords_list.addItem("No keywords available")

    def _populate_links(self):
        """Populate links table."""
        links = getattr(self.collection, "links", None)
        if not links:
            self.links_table.setRowCount(1)
            self.links_table.setItem(0, 0, QtWidgets.QTableWidgetItem("No links available"))
            return

        self.links_table.setRowCount(len(links))

        for row, link in enumerate(links):
            # Title
            title = getattr(link, "title", None) or ""
            self.links_table.setItem(row, 0, QtWidgets.QTableWidgetItem(title))

            # Type (media type)
            media_type = getattr(link, "media_type", None) or getattr(link, "type", None)
            self.links_table.setItem(row, 1, QtWidgets.QTableWidgetItem(media_type or ""))

            # Rel
            rel = getattr(link, "rel", None) or ""
            self.links_table.setItem(row, 2, QtWidgets.QTableWidgetItem(rel))

            # URL (href)
            href = getattr(link, "href", None) or getattr(link, "target", None) or ""
            self.links_table.setItem(row, 3, QtWidgets.QTableWidgetItem(href))

        # Resize columns to content
        self.links_table.resizeColumnsToContents()
