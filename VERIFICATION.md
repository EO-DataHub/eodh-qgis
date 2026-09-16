# ArcGIS parity verification

Implementation reference: the local `eodh-arcgis` plugin, especially its usage guide,
STAC and workspace services, commercial provider capability table, quote/order
request models, and Search / Results / Workspace views.

## Ticket coverage

| Requirement | Implementation |
| --- | --- |
| Rename plugin | `metadata.txt`: Access and run workflows on the EODH |
| Remove CWL tag | Removed from registry metadata |
| Explain qpip and dependencies | `USAGE_GUIDE.md`, linked from README and included in the plugin ZIP |
| QGIS 4 and QGIS 3 LTR | `qgis.PyQt`, scoped enums, runtime-independent branding; tested on Qt 6 and Qt 5 |
| Remove workflow navigation | Plugin entry point opens `HubDock` with Search, Results and Workspace only |
| Public/commercial catalogue groups | Recursive discovery, provider labels, cycle handling, pagination and owning search endpoints |
| Search filters | Collection extent/date defaults, map extent, rectangle drawing, GeoJSON/shapefile/GeoPackage import and conditional cloud cover |
| Results | Thumbnail timeline, inline cards, synchronized selection, metadata, cached paging, asset checkboxes and configured Quick view |
| Temporary map geometry | Polygon/MultiPolygon footprints, selected highlight, independent AOI visibility and cleanup |
| Commercial flow | Airbus Optical/SAR, Planet and Open Cosmos capabilities; independent inline quotes, provider guidance and final purchase confirmation |
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
- Ran twelve pure-Python contract tests in `tests/test_hub_contract.py` and
  `tests/test_presentation.py`, including default asset selection, metadata/overlap
  formatting and the exact ArcGIS TiTiler render query parameters.
- Updated the login against ArcGIS `LoginView.xaml`: single centered logo,
  Segoe UI typography, matching orbital paths and dots, stacked fields, exact
  copy and both documentation links/icons. Production is fixed; credentials are
  remembered automatically. The login has no header or usage-guide button.
- Visually checked the updated login in QGIS 4 and QGIS 3 LTR, including a narrow
  QGIS 4 dock. Ran `tests/qgis_login_check.py` on both runtimes: Production routing,
  empty-key validation, automatic save/restore, expired-key cleanup and sign-out.
  Persistence and API calls in this test use isolated fakes, not live credentials.
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
- Follow-up screen pass compared the current ArcGIS signed-in Search and
  Workspace screens and their XAML/view models with QGIS. Updated the compact
  workspace header, footer, catalog labels/links, collection extent defaults,
  calendar fields, cloud slider, inline result cards, thumbnail timeline,
  commercial field rows, purchase copy, workspace cards and expandable files.
- Ran `tests/qgis_screen_check.py` on QGIS 4.2.2 and 3.44.14 LTR. It checks
  collection dates/AOI defaults, disabled search without AOI, newest timeline
  selection and date labels, inline assets and defaults, outside-AOI filtering,
  cached next/previous pages, omitted totals and paging errors, independent
  commercial quotes, declining purchase confirmation, workspace selection
  persistence, and a GeoPackage with layers in different coordinate systems.
- In the updated QGIS 4 UI, a live Sentinel-2 search returned 72,037 matches,
  with 50 inline cards. Expanded assets and added the Natural Color Quick view
  XYZ layer. A separate authenticated request using the same render URL returned
  a valid 256 × 256 JPEG tile. Native map tile rendering was not established in
  the initial layer-creation check. The final thumbnail strip was visually
  verified with visible images and date labels after fixing Qt widget clipping.
- In QGIS 3 LTR, visually verified the updated signed-in search, commercial
  catalog selection, delivered workspace cards and expanded file checkboxes.
- The live Airbus search exposed nullable match counts. Pagination now ignores
  null counts, preserves known totals on later pages and falls back to the
  returned item count when no total is available; both Qt runtime checks cover it.
- Repeated the live Airbus PHR search in the fixed QGIS 3 LTR plugin: 3,826,860
  matches, 50 cards, and visible per-card licence, bundle, GB country and Get Quote
  controls. Checked the corrected thumbnail timeline in that runtime as well.
- QGIS 3 LTR successfully performed a live Airbus catalogue search and displayed
  the empty-results guidance for the chosen current-date range and map extent.
- Built `dist/eodh_qgis.zip` and checked that its contents do not contain the
  supplied API key. Development profiles, installers and credentials are excluded.

## Loading and streaming follow-up (2026-09-16, version 0.2.7)

- Reviewed the supplied recording and traced transient native windows to result
  and workspace buttons shown before they had a parent. Both card types now
  assign parents first; the screen regression watches top-level show events.
- Collection menus now show up to 20 rows instead of 10. Visually checked the
  taller menu and live collection/search loading with Windows computer use.
- Compared ArcGIS LayerService's remote-first raster loading with QGIS. GeoTIFF
  and COG assets now use GDAL `/vsicurl` range reads, with STAC RGB band mapping.
  Servers without streaming support require explicit consent for a full download.
- A live Sentinel-2 ARD COG at CEDA was 2,034,369,365 bytes with nine overviews.
  Opening it transferred 32,768 bytes. Visually verified native QGIS map rendering
  and zooming; the QGIS 4 overview/detail session transferred 82,132,992 bytes,
  rather than the entire file. Both QGIS 4.2.2 and 3.44.14 opened and rendered it.
  This VM reports a missing preferred EPSG:27700-to-3857 transform; native
  EPSG:27700 rendering was also checked independently of that installation warning.
- `qgis_streaming_check.py` passes on both installed QGIS versions, including real
  plugin startup, overview and finer-detail reads (917,809 of 64,409,758 fixture
  bytes), scoped authorization, cross-host redirects, credential clearing and
  refusing an automatic full download. Thirteen pure contract tests pass, as do
  both native screen suites and Ruff lint/format checks.
- Built the credential-scanned ZIP and byte-verified all 65 installed files in
  both normal default profiles. Reloaded both running plugins without closing
  the user's projects. QGIS 4 reconnected automatically; LTR requires its key again.

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

Explicit full-file downloads and NetCDF downloads are local temporary files,
retained so created layers remain usable in the current session. Copy downloaded
imagery to durable storage for long-lived projects. Streamed COG/GeoTIFF projects
keep remote URLs; protected layers require reconnecting to the same workspace. AOI overlap uses a planar WGS84 approximation. Antimeridian-crossing
AOIs must be split into separate searches.
