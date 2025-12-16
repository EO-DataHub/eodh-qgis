"""Mock STAC API server for integration testing."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


class MockStacHandler(BaseHTTPRequestHandler):
    """Mock STAC API endpoint handler.

    Handles basic STAC API endpoints for testing:
    - /catalogs - List available catalogs
    - /collections - List collections
    - /search - Search for items
    """

    # Sample test data
    CATALOGS: list[dict[str, Any]] = [
        {
            "id": "test-catalog",
            "title": "Test Catalog",
            "description": "Test catalog for unit tests",
        },
    ]

    COLLECTIONS: list[dict[str, Any]] = [
        {
            "id": "test-collection",
            "title": "Test Collection",
            "description": "Test collection for unit tests",
            "extent": {
                "spatial": {"bbox": [[-180, -90, 180, 90]]},
                "temporal": {"interval": [["2020-01-01T00:00:00Z", None]]},
            },
        },
    ]

    ITEMS: list[dict[str, Any]] = [
        {
            "type": "Feature",
            "id": "test-item-1",
            "collection": "test-collection",
            "datetime": "2024-01-15T10:30:00Z",
            "bbox": [-10.5, 45.25, 20.75, 60.125],
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-10.5, 45.25],
                        [20.75, 45.25],
                        [20.75, 60.125],
                        [-10.5, 60.125],
                        [-10.5, 45.25],
                    ]
                ],
            },
            "properties": {"datetime": "2024-01-15T10:30:00Z"},
            "assets": {
                "data": {
                    "href": "https://example.com/test-item-1/data.tif",
                    "type": "image/tiff; application=geotiff",
                    "roles": ["data"],
                },
                "thumbnail": {
                    "href": "https://example.com/test-item-1/thumbnail.png",
                    "type": "image/png",
                    "roles": ["thumbnail"],
                },
            },
        },
        {
            "type": "Feature",
            "id": "test-item-2",
            "collection": "test-collection",
            "datetime": "2024-01-16T14:00:00Z",
            "bbox": [-5.0, 50.0, 15.0, 55.0],
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-5.0, 50.0],
                        [15.0, 50.0],
                        [15.0, 55.0],
                        [-5.0, 55.0],
                        [-5.0, 50.0],
                    ]
                ],
            },
            "properties": {"datetime": "2024-01-16T14:00:00Z"},
            "assets": {
                "visual": {
                    "href": "https://example.com/test-item-2/visual.tif",
                    "type": "image/tiff; application=geotiff; profile=cloud-optimized",
                    "roles": ["visual", "data"],
                },
            },
        },
    ]

    def log_message(self, format: str, *args) -> None:
        """Suppress HTTP server logging."""
        pass

    def do_GET(self) -> None:
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        query_params = parse_qs(parsed.query)

        if "/catalogs" in path:
            self._respond_json(self.CATALOGS)
        elif "/collections" in path and "/items" in path:
            self._respond_items(query_params)
        elif "/collections" in path:
            self._respond_json(self.COLLECTIONS)
        elif "/search" in path:
            self._respond_items(query_params)
        else:
            self._respond_json(
                {"type": "Catalog", "id": "root", "description": "Root catalog"}
            )

    def do_POST(self) -> None:
        """Handle POST requests (search endpoint)."""
        if "/search" in self.path:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                params = json.loads(body) if body else {}
            except json.JSONDecodeError:
                params = {}
            self._respond_items(params)
        else:
            self.send_error(404)

    def _respond_json(self, data: Any) -> None:
        """Send JSON response."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _respond_items(self, params: dict) -> None:
        """Respond with items, applying optional filters."""
        items = self.ITEMS.copy()

        # Apply limit
        limit = params.get("limit", [100])
        if isinstance(limit, list):
            limit = int(limit[0])
        items = items[:limit]

        # Build FeatureCollection response
        response = {
            "type": "FeatureCollection",
            "features": items,
            "numberMatched": len(self.ITEMS),
            "numberReturned": len(items),
        }
        self._respond_json(response)


class MockStacServer:
    """Context manager for mock STAC server.

    Usage:
        with MockStacServer() as server:
            # Make requests to server.url
            response = requests.get(f"{server.url}/catalogs")

    Attributes:
        port: Port number the server is listening on
        url: Full URL to the mock server (e.g., "http://localhost:8888")
    """

    def __init__(self, port: int = 0) -> None:
        """Initialize mock server.

        Args:
            port: Port to listen on (0 = auto-assign available port)
        """
        self.port = port
        self.server: HTTPServer | None = None
        self.thread: threading.Thread | None = None

    def __enter__(self) -> MockStacServer:
        """Start the mock server."""
        self.server = HTTPServer(("localhost", self.port), MockStacHandler)
        # Get the actual port if 0 was specified
        self.port = self.server.server_address[1]

        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        return self

    def __exit__(self, *args) -> None:
        """Stop the mock server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()  # Properly close the socket
            self.server = None
        self.thread = None

    @property
    def url(self) -> str:
        """Get the server URL."""
        return f"http://localhost:{self.port}"
