# EODH Plugin for QGIS — Usage Guide

The EODH plugin brings the [Earth Observation Data Hub](https://eodatahub.org.uk) into QGIS with the same Search, Results and Workspace flow as the ArcGIS Pro add-in.

## Requirements and installation

- QGIS 4, or QGIS 3.44 LTR, on a supported desktop system.
- An EODH workspace name and current Workspace API key.
- An internet connection for catalogue search and downloading imagery.

Install **Access and run workflows on the EODH** using **Plugins → Manage and Install Plugins**. For a development ZIP, use **Install from ZIP**. Open the EODH toolbar button or **Web → EODH → Earth Observation Data Hub**.

### What is qpip?

**qpip** is a separate QGIS plugin that manages Python packages required by other plugins. It reads this plugin's `requirements.txt`, asks before installing missing packages, and installs them under the active QGIS profile's `python/dependencies` directory. Each profile can have its own dependencies. See the [qpip documentation](https://github.com/opengisch/qpip#usage-end-user). It is not an EODH account or a satellite-data subscription.

The package prompt for this plugin lists:

| Package | Purpose |
| --- | --- |
| `defusedxml` | Safer XML parsing used by the plugin's existing data utilities. |
| `pyeodh` | EODH Python client used by the retained API/data utility modules; includes its own Python dependencies. |
| `truststore` | Uses the operating system's trusted certificate store for HTTPS connections. |

Review qpip's full dependency list before agreeing; it can include dependencies required by these packages. You are agreeing to install software, not to purchase commercial imagery. If you decline, features that need missing packages may be unavailable. Restart QGIS if qpip requests it. QGIS itself supplies Qt, GDAL and its Python bindings; do not install a separate PyQt wheel into QGIS.

## Signing in

1. Enter your **Workspace name** and **Workspace API key**. Paste the API Key, not the Token ID.
2. Select **Connect**. The plugin always connects to Production.

Credentials are automatically saved in the encrypted QGIS authentication manager.
QGIS may ask you to unlock or configure its authentication database. Saved
credentials are validated automatically when the plugin opens; invalid saved keys
are cleared and the sign-in screen displays the service error. If QGIS cannot save
the key, the plugin tells you that it will only be available for this session.

**Workspace documentation** opens the EODH credentials guide. **Get workspace
credentials** opens the portal for the workspace entered in the form. This usage
guide is linked from the repository README and included in the plugin ZIP.

Workspace API keys expire after at most 30 days and are not renewed automatically. If access is denied, check the workspace and create or copy a current key from the [workspace credentials page](https://docs.eodatahub.org.uk/Getting-Started/workspaces/workspace-credentials/).

**Switch** and **Log out** return to the login screen and clear saved EODH credentials, results and temporary map overlays. Credentials are never written into the QGIS project. EODH bearer credentials are sent only to the Production EODH host, including when loading assets.

## Searching for data

Search provides exactly two curated catalogue groups: **Public** and **Commercial**. The plugin discovers descendant catalogues and collections and displays a sorted **Provider — Collection** list. Type in the collection picker to find a collection. Internal and workspace catalogues are not search roots.

Selecting a collection applies its published spatial and temporal extents. You can replace the area with **Draw on Map** (drag a rectangle), **Map Extent**, or **Import AOI**. Import accepts GeoJSON/JSON polygons, shapefiles and GeoPackages; projected vector extents are transformed to WGS84. The combined bounding box is searched without adding the imported file to the map. **Clear** removes the AOI and hides result footprints. Search requires an area and a collection. Areas crossing the antimeridian should be searched separately on each side.

Dates follow the selected collection's temporal extent, with today for an open end and one month ago when no start is published. The end date includes the whole day. **Max Cloud Cover** appears when the collection publishes cloud metadata. At 100%, no cloud predicate is sent. Select **Search** to open Results. If discovery fails, select the other catalog group and switch back to retry.

## Results, timeline and footprints

The thumbnail timeline is ordered by acquisition date and initially selects the newest dated scene. It shares its selection with the inline result cards. Arrow buttons step through dated scenes; **‹ Previous** and **Next ›** browse cached result pages. Page errors retain the current results. An empty search displays **No results found**.

**Show footprints** is initially enabled. Valid Polygon and MultiPolygon geometries on the current page appear as blue outlines, with the selected scene outlined in gold. They never become project layers. Hiding footprints, clearing results, starting another search, signing out or closing the dock removes them. **Show AOI** independently controls the blue AOI outline and faint fill.

Each card includes item and collection IDs, acquisition time, resolution, cloud cover, locational accuracy, licence and AOI overlap where available. Items with zero bounding-box overlap are excluded from the current page and counted in its summary. AOI overlap is a planar WGS84 area approximation.

Select **N loadable / N total assets** to expand a card. Supported **COG**, **GeoTIFF** and **NetCDF** files can be checked; metadata and thumbnail assets remain visible but disabled. Collection-specific defaults follow ArcGIS. **Load Selected Assets** opens COG and GeoTIFF assets remotely in a background task. QGIS uses HTTP byte-range requests to fetch overview pixels when zoomed out and higher-resolution blocks as you zoom in or pan. It does not first download the complete raster. GeoTIFFs without internal overviews or tiling can require more data. If streaming is unavailable, the plugin automatically downloads the complete file and then loads it. Download progress is shown in the status area. Double-clicking a card with default assets loads its selection; otherwise it expands the assets. NetCDF assets still download before their variables are loaded using the existing georeferencing support. Streamed layers retain their remote source in saved projects; an internet connection is required. For protected EODH streams, connect to the same workspace to restore authentication after reopening a project. API keys are kept out of raster source URLs and project files. Downloaded temporary files remain available for loaded layers; copy needed data to durable storage before saving a long-lived project.

**Quick view** appears when the collection has a supported render configuration and the item contains its required assets. It adds the same default TiTiler rendering as ArcGIS as an XYZ layer. The layer references QGIS's encrypted authentication configuration, never the API key itself.

## Commercial quotes and orders

| Provider | Licence | Product bundles | Other fields |
| --- | --- | --- | --- |
| Airbus Optical | Nine provider choices | Visual, General Use, Basic, Analytic | End-user country |
| Airbus SAR | Three provider choices | SSC, MGD, GEC, EEC | Orbit; resolution except SSC; projection except SSC/MGD |
| Planet | No licence picker | Visual, General Use, Basic, Analytic | None |
| Open Cosmos | No licence picker | No bundle picker | AOI, when supplied |

1. Complete all visible provider fields.
2. Select **Get Quote** and review the returned value, units and message.
3. Review **Provider account and licensing guidance**.
4. Select **Purchase**. The **EODH — Confirm Order** dialog states the quoted price and explains that the action is irreversible. **No** is the default. Successful submission displays **Ordered — check workspace for delivery status**.

A quote belongs to the exact item, provider, AOI, licence, bundle, country and applicable radar options. Each result card maintains its own quote. Changing an input clears it; a stale response cannot enable ordering. The country field defaults to GB and accepts up to three characters. After an order error, check Workspace before attempting another purchase, since a network failure may occur after the backend accepted an order.

If provider credentials are missing, link the Airbus or Planet account in EODH Workspace settings. See [linked accounts guidance](https://docs.eodatahub.org.uk/Getting-Started/workspaces/linked-accounts/).

## Workspace commercial data

The Workspace tab shows **Commercial data** for the connected workspace. **Provider:** and **Status:** filters list values returned by the service. Cards show the provider, collection, item ID, status, order details and backend messages. Delivered records with supported assets expose **Available loadable files**; expand it, select files and choose **Load into map**. Filtering retains selections and expanded cards. Pending, processing and failed records cannot be loaded. Use **Refresh** for delivery updates or **Retry** after an error.

This view follows the ArcGIS add-in: it does not include workflow execution tabs, members or a raw object-store browser. The plugin's registry name is retained as requested by the project ticket.

## Troubleshooting

- **Cannot connect:** check the workspace, network and API key; replace expired keys.
- **No collections or results:** select another catalog group and switch back, choose another collection, broaden dates or choose a different AOI.
- **No loadable assets:** metadata and thumbnails are not raster assets. Commercial data must be delivered first.
- **Dependencies unavailable:** open qpip, review its package prompt, and restart QGIS after installation.
- **Usage guide:** follow the README link or open `USAGE_GUIDE.md` from the installed plugin directory.
