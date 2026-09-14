# ArcGIS parity verification

Implementation reference: the local `eodh-arcgis` plugin, especially its usage guide,
STAC and workspace services, commercial provider capability table, quote/order
request models, and Search / Results / Workspace views.

## Ticket coverage

| Requirement | Implementation |
| --- | --- |
| Rename plugin | `metadata.txt`: Access and run workflows on the EODH |
| Remove CWL tag | Removed from registry metadata |
| Explain qpip and dependencies | `USAGE_GUIDE.md`, linked from README and available inside the dock |
| QGIS 4 and QGIS 3 LTR | `qgis.PyQt`, scoped enums, runtime-independent branding; tested on Qt 6 and Qt 5 |
| Remove workflow navigation | Plugin entry point opens `HubDock` with Search, Results and Workspace only |
| Public/commercial catalogue groups | Recursive discovery, provider labels, cycle handling, pagination and owning search endpoints |
| Search filters | Map extent, rectangle drawing, GeoJSON import, dates and conditional cloud cover |
| Results | Acquisition timeline, synchronized selection, metadata, thumbnails, paging and asset checkboxes |
| Temporary map geometry | Polygon/MultiPolygon footprints, selected highlight, independent AOI visibility and cleanup |
| Commercial flow | Airbus Optical/SAR, Planet and Open Cosmos capabilities; quote context, licensing acceptance and final purchase confirmation |
| Workspace | Authenticated-workspace commercial records, provider/status filters, backend messages and completed-record asset loading |

The old workflow/widget modules remain as inactive legacy source for existing unit
tests; they are no longer reachable through the plugin's menu or toolbar.

## Checks performed on this VM

- Installed QGIS **4.2.2** (Qt **6.11.0**) first, then QGIS **3.44.14 LTR** (Qt **5.15.13**).
- Ran `tests/qgis_runtime_check.py` under both installed QGIS Python launchers.
  Checks cover actual dock widgets, three tabs, curated roots, valid footprint
  rendering without project layers, synchronized timeline selection, quote
  invalidation, stale asynchronous quote responses, AOI changes and workspace
  loading gates.
- Ran nine pure-Python contract tests in `tests/test_hub_contract.py`.
- Repository Ruff lint and format checks pass. Pyright reports zero errors;
  warnings concern unavailable QGIS/optional package type information in the
  standalone checking environment. `validate-pyproject` passes.
- Used the supplied credential file for Production authentication and read-only
  catalogue discovery: 26 Public and 12 Commercial collections were found.
- Used Windows computer use to inspect the ArcGIS sign-in reference, QGIS 4's
  sign-in/search/results UI, and QGIS 3 LTR's active dock and commercial catalogue
  selector.
- In QGIS 4, performed a live Sentinel-2 search using the map extent and default
  two-month date range: 3,635 matches, 50 on the first page. Verified the next
  page, thumbnails, item metadata, footprint visibility and real COG loading.
  A selected true-color COG became an RGB raster layer in the map.
- Loaded the included EOCIS sea-ice NetCDF sample with the QGIS 4 runtime:
  three valid raster layers were created.
- QGIS 4's Workspace tab retrieved existing Airbus commercial records, including
  succeeded status, order IDs, timestamps and supported delivered COG assets.
- QGIS 3 LTR successfully performed a live Airbus catalogue search and displayed
  the empty-results guidance for the chosen current-date range and map extent.
- Built `dist/eodh_qgis.zip` and checked that its contents do not contain the
  supplied API key. Development profiles, installers and credentials are excluded.

## Boundaries

No commercial quote or purchase was submitted to the live service. Commercial
request payloads and UI state transitions are verified against the ArcGIS contract
and local tests. Provider fulfillment cannot be verified without placing an order.

The historical Docker-based test suite has not been run on this Windows VM.
A local QGIS 3 run of its 274 legacy tests passed 114 tests before the Python
process exited without a pytest summary in `TestJobsWidget`; that historical
workflow widget is no longer reachable from the plugin. This is an incomplete
legacy-suite run, not a full pass. Legacy test packaging still includes the old
compiled UI resources. New contract tests are wired into CI, and the current
dock is tested directly against both installed QGIS versions.

Asset downloads are local temporary files, retained so the created layers remain
usable in the current session. Copy imagery to durable storage for long-lived
projects. AOI overlap uses a planar WGS84 approximation. Antimeridian-crossing
AOIs must be split into separate searches.
