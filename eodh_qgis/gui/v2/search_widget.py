import pyeodh
from qgis.PyQt import QtWidgets


class SearchWidget(QtWidgets.QWidget):
    def __init__(self, creds: dict[str, str], parent=None):
        """Constructor."""
        super(SearchWidget, self).__init__(parent)
        self.creds = creds

        layout = QtWidgets.QVBoxLayout()

        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Enter search term...")
        layout.addWidget(self.search_input)

        self.search_button = QtWidgets.QPushButton("Search")
        self.search_button.clicked.connect(self.on_search_clicked)
        layout.addWidget(self.search_button)

        self.results_text = QtWidgets.QTextEdit()
        self.results_text.setReadOnly(True)
        layout.addWidget(self.results_text)

        self.setLayout(layout)

    def on_search_clicked(self):
        """Handle search button click."""
        search_term = self.search_input.text()
        if not search_term:
            return

        self.results_text.clear()
        self.results_text.append(f"Searching for: {search_term}...")

        try:
            client = pyeodh.Client(
                username=self.creds["username"], token=self.creds["token"]
            )
            catalog_service = client.get_catalog_service()
            results = catalog_service.collection_search(query=search_term, limit=10)

            self.results_text.clear()
            count = 0
            for item in results:
                count += 1
                self.results_text.append(
                    f"{count}. {item.id} - {item.title or 'No title'}"
                )

            if count == 0:
                self.results_text.append("No results found.")
        except Exception as e:
            self.results_text.append(f"Error: {str(e)}")
