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

1. Choose Production, Staging or Test.
2. Enter your **Workspace name** and **Workspace API key**. Paste the API Key, not the Token ID.
3. Optionally enable **Remember credentials in QGIS authentication manager**. QGIS may ask you to unlock or configure its authentication database. Otherwise the key stays in memory for this session.
4. Select **Connect**.

Workspace API keys expire after at most 30 days and are not renewed automatically. If access is denied, check the workspace and create or copy a current key from the [workspace credentials page](https://docs.eodatahub.org.uk/Getting-Started/workspaces/workspace-credentials/).

**Sign Out** clears saved EODH credentials, results and temporary map overlays. Credentials are never written into the QGIS project. EODH bearer credentials are sent only to the selected EODH host, including when loading assets.

## Searching for data

Search provides exactly two curated catalogue groups: **Public** and **Commercial**. The plugin discovers descendant catalogues and collections and displays a sorted **Provider — Collection** list. Type in the collection picker to find a collection. Internal and workspace catalogues are not search roots.

Define your area of interest with **Draw on Map** (drag a rectangle), **Map Extent**, or **Import GeoJSON**. Imported Polygon and MultiPolygon boundaries, including FeatureCollections, are searched using their combined WGS84 bounding box. **Clear** removes the AOI. Areas crossing the antimeridian should be searched separately on each side.

Dates default to the last two calendar months. The end date includes the whole day. **Max Cloud Cover** appears when the selected collection publishes cloud metadata. At 100%, no cloud predicate is sent. Select **Search** to open Results. Use **Refresh collections / Retry** if discovery fails.

## Results, timeline and footprints

The acquisition timeline and result list share their selection. Select a scene in either view to see its metadata, thumbnail and assets. **Previous** and **Next** browse result pages. Empty results include a suggestion to broaden the search.

**Show footprints** is enabled by default. Valid Polygon and MultiPolygon geometries on the current page appear as temporary canvas overlays, with the selected scene emphasized. They never become project layers. Hiding footprints, clearing results, starting another search, signing out or closing the dock removes them. **Show AOI** independently controls the AOI overlay. **Zoom to item** fits the map to the selected footprint.

Result details include item and collection IDs, acquisition time, resolution, cloud cover, locational accuracy, licence and AOI overlap where available. AOI overlap is a planar WGS84 area approximation.

Check supported **COG**, **GeoTIFF** or **NetCDF** assets and choose **Load Selected Assets**, or double-click the result. Files are downloaded locally in a background task before loading, so protected assets can be authenticated without storing a token in a layer source. NetCDF data variables use the existing georeferencing support. Downloaded files remain in the local temporary directory so loaded layers keep working; copy needed data to a durable location before saving a long-lived project.

## Commercial quotes and orders

| Provider | Licence | Product bundles | Other fields |
| --- | --- | --- | --- |
| Airbus Optical | Nine provider choices | Visual, General Use, Basic, Analytic | End-user country |
| Airbus SAR | Three provider choices | SSC, MGD, GEC, EEC | Orbit; resolution except SSC; projection except SSC/MGD |
| Planet | No licence picker | Visual, General Use, Basic, Analytic | None |
| Open Cosmos | No licence picker | No bundle picker | AOI, when supplied |

1. Complete all visible provider fields.
2. Select **Get Quote** and review the returned value, units and message.
3. Review the linked commercial documentation and accept the applicable licensing terms.
4. Select **Place Order**. The final confirmation identifies the item and quote and explains that the purchase is irreversible. **No** is the default.

A quote belongs to the exact item, provider, AOI, licence, bundle, country and applicable radar options. Changing an input clears the quote and licensing acceptance. A quote arriving after an input change cannot enable ordering. After an order error, check Workspace before attempting another purchase, since a network failure may occur after the backend accepted an order.

If provider credentials are missing, link the Airbus or Planet account in EODH Workspace settings. See [linked accounts guidance](https://docs.eodatahub.org.uk/Getting-Started/workspaces/linked-accounts/).

## Workspace commercial data

The Workspace tab shows commercial records for the connected workspace. Filter by provider and status; review order IDs, dates and backend messages. Completed records with supported assets allow asset selection and **Load into map**. Pending, processing and failed records cannot be loaded. Use **Refresh / Retry** for updated delivery status or after an error.

This view follows the ArcGIS add-in: it does not include workflow execution tabs, members or a raw object-store browser. The plugin's registry name is retained as requested by the project ticket.

## Troubleshooting

- **Cannot connect:** check the environment, workspace, network and API key; replace expired keys.
- **No collections or results:** use Retry, choose another collection, broaden dates or clear the AOI.
- **No loadable assets:** metadata and thumbnails are not raster assets. Commercial data must be delivered first.
- **Dependencies unavailable:** open qpip, review its package prompt, and restart QGIS after installation.
- **Usage guide:** the dock's Usage guide button opens this guide locally.
