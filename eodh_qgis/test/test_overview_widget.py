"""Tests for OverviewWidget, focused on catalog fetching logic."""

import unittest
from unittest.mock import MagicMock, patch

from eodh_qgis.gui.overview_widget import OverviewWidget
from eodh_qgis.test.utilities import get_qgis_app


class TestGetAllCatalogs(unittest.TestCase):
    """Tests for _get_all_catalogs pagination handling."""

    @classmethod
    def setUpClass(cls):
        cls.QGIS_APP = get_qgis_app()
        assert cls.QGIS_APP is not None

    def _make_widget(self):
        """Create an OverviewWidget with mocked API calls."""
        with patch.object(OverviewWidget, "_populate_catalogue_dropdown"):
            widget = OverviewWidget(parent=None)
        return widget

    def _make_catalog_service(self, pages):
        """Create a mock CatalogService that returns paginated responses.

        Args:
            pages: list of (catalogs_data, next_url_or_none) tuples.
                Each catalogs_data is a list of dicts with catalog info.
        """
        mock_service = MagicMock()
        mock_service._pystac_object.self_href = "https://example.com/stac"

        call_count = 0

        def mock_request_json(method, url):
            nonlocal call_count
            if call_count < len(pages):
                catalogs_data, next_url = pages[call_count]
            else:
                # Past the defined pages - return empty (shouldn't happen
                # if test is correct, but prevents true infinite loop in test)
                catalogs_data, next_url = [], None
            call_count += 1

            links = []
            if next_url:
                links.append({"rel": "next", "href": next_url})

            data = {"catalogs": catalogs_data, "links": links}
            return {}, data

        mock_service._client._request_json = mock_request_json
        return mock_service, lambda: call_count

    def _make_catalog_data(self, cat_id, title=None):
        """Create minimal STAC catalog data dict."""
        return {
            "id": cat_id,
            "type": "Catalog",
            "title": title or cat_id,
            "description": f"Test catalog {cat_id}",
            "stac_version": "1.0.0",
            "links": [
                {
                    "rel": "self",
                    "href": f"https://example.com/stac/catalogs/{cat_id}",
                }
            ],
        }

    def test_single_page_returns_all_catalogs(self):
        """When API returns one page with no next link, all catalogs are returned."""
        widget = self._make_widget()
        catalogs_data = [
            self._make_catalog_data("cat-1"),
            self._make_catalog_data("cat-2"),
        ]
        mock_service, _ = self._make_catalog_service([(catalogs_data, None)])

        result = widget._get_all_catalogs(mock_service)

        self.assertEqual(len(result), 2)

    def test_multi_page_returns_all_catalogs(self):
        """When API paginates, catalogs from all pages are collected."""
        widget = self._make_widget()
        page1 = [self._make_catalog_data(f"cat-{i}") for i in range(10)]
        page2 = [self._make_catalog_data(f"cat-{i}") for i in range(10, 17)]

        mock_service, _ = self._make_catalog_service(
            [
                (page1, "https://example.com/stac/catalogs?token=page2"),
                (page2, None),
            ]
        )

        result = widget._get_all_catalogs(mock_service)

        self.assertEqual(len(result), 17)

    def test_empty_response_returns_empty_list(self):
        """When API returns no catalogs, empty list is returned."""
        widget = self._make_widget()
        mock_service, _ = self._make_catalog_service([([], None)])

        result = widget._get_all_catalogs(mock_service)

        self.assertEqual(len(result), 0)

    def test_circular_next_link_does_not_loop_forever(self):
        """When API returns a circular next link, fetching stops at a safe limit.

        This is the key bug: without a max-page guard, a circular next link
        would cause _get_all_catalogs to loop forever, freezing QGIS.
        """
        widget = self._make_widget()
        # Every page points back to itself — infinite loop
        circular_page = [self._make_catalog_data("cat-loop")]
        circular_url = "https://example.com/stac/catalogs?token=loop"

        # Create enough pages to exceed any reasonable limit
        pages = [(circular_page, circular_url)] * 200

        mock_service, get_call_count = self._make_catalog_service(pages)

        result = widget._get_all_catalogs(mock_service)

        # Should have stopped well before 200 iterations
        self.assertLess(get_call_count(), 200)
        # Should still return the catalogs it did fetch
        self.assertGreater(len(result), 0)

    @patch("eodh_qgis.gui.overview_widget.QgsMessageLog")
    def test_malformed_catalog_is_skipped_and_logged(self, mock_log):
        """When a catalog entry causes an exception, it's skipped with a log."""
        widget = self._make_widget()
        catalogs_data = [
            self._make_catalog_data("good-cat"),
            {"bad": "data"},  # Missing required fields
            self._make_catalog_data("another-good-cat"),
        ]
        mock_service, _ = self._make_catalog_service([(catalogs_data, None)])

        result = widget._get_all_catalogs(mock_service)

        # Good catalogs should be returned, bad one skipped
        self.assertEqual(len(result), 2)
        # Warning should have been logged
        mock_log.logMessage.assert_called()


if __name__ == "__main__":
    unittest.main()
