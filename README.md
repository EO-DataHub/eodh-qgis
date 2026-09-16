# eodh-qgis Plugin

[![codecov](https://codecov.io/github/EO-DataHub/eodh-qgis/graph/badge.svg?token=N2VQBHVZN8)](https://codecov.io/github/EO-DataHub/eodh-qgis)

A QGIS plugin for Earth Observation Data Hub (EODH) catalogue search, imagery loading,
commercial quotes and orders, and workspace commercial records. Its dockable Search,
Results and Workspace interface follows the EODH ArcGIS Pro add-in.

See the [usage guide](USAGE_GUIDE.md) for installation, qpip dependencies, signing in,
search filters, thumbnail timeline, Quick view, asset loading and commercial ordering.

## Installation

### From QGIS repository

1. Go to menu Plugins -> All
2. Search for `Access and run workflows on the EODH`
3. Click Install Plugin
4. Review the [qpip dependency explanation](USAGE_GUIDE.md#what-is-qpip) before agreeing to install the listed packages.

### Manual

1. Download archive for your platform from releases
2. Open QGIS
3. Go to menu Plugins -> Manage and Install Plugins...
4. Select `Install from ZIP...`
5. Select the downloaded archive
6. Click `Install Plugin`
7. Review qpip's package prompt; the [usage guide](USAGE_GUIDE.md#what-is-qpip) explains the packages and their purposes.

### Version compatibility

The supported baseline is QGIS 3.44 LTR and QGIS 4, using their bundled Python and
`qgis.PyQt` bindings. No separately installed PyQt wheel or resource compiler is
needed to build the current dock UI. CI runs native compatibility checks on
QGIS 3.44 / Qt 5 and QGIS 4.2 / Qt 6.

## Usage

When opening the plugin for the first time, you need to configure authentication credentials to access EODH APIs.

1. Enter your workspace name and Workspace API key. The plugin connects to Production and remembers credentials securely.
2. Select Connect, then choose a Public or Commercial collection on Search.
3. Browse Results or open Workspace to review commercial orders.

The legacy workflow execution navigation is removed from the active plugin.

## Development

### Flatpak and VSCode

To setup language server support in VSCode if you've installed QGIS from Flatpak:

1. Find pyqgis location

   ` find / -type d -wholename "*share/qgis/python/qgis" 2> /dev/null`

2. Set the `PYTHONPATH` env variable for VSCode by creating a `.env` file with the following content:

   `PYTHONPATH="/path/to/pyqgis"`

3. Restart VSCode

### Developer workflow

1. Make changes
2. Deploy changes to plugin directory

   1. Locate the QGIS plugin directory, **make sure the directory named after the plugin is included in the path** e.g. `~/.var/app/org.qgis.qgis/data/QGIS/QGIS3/profiles/default/python/plugins/eodh_qgis`
   2. (Optional) Set this path as an env variable in `.env` named `EODH_QGIS_PATH`
   3. Run `python deploy.py <path to plugin directory>` (Path can be ommited if already set as an env variable in prev. step)

3. Reload plugin

### Testing

1. `make check` will run code formatting and linting checks.

2. `make test` will run tests against a running QGIS instance in a docker container.

3. `python -m unittest discover -s tests -v` runs the transport/contract regressions without QGIS.

4. Run `tests/qgis_runtime_check.py` with each QGIS installation's Python launcher
   to check actual Qt widgets, map overlays, quote invalidation and workspace asset gates.

5. Run `tests/qgis_login_check.py` and `tests/qgis_screen_check.py` with the same
   launchers for login state, collection defaults, projected AOI import, inline
   cards, timeline dates, page caching/errors, purchase cancellation and workspace
   selection persistence. These checks use local fixtures and do not place orders.
