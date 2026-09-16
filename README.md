# EODH Plugin for QGIS

[![codecov](https://codecov.io/github/EO-DataHub/eodh-qgis/graph/badge.svg?token=N2VQBHVZN8)](https://codecov.io/github/EO-DataHub/eodh-qgis)

Search, filter, preview, and load datasets from the UK EO Data Hub.

EODH for QGIS supports catalogue search, imagery loading, commercial quotes and
orders, and workspace commercial records. Its dockable Search, Results and Workspace
interface follows the EODH ArcGIS Pro add-in.

See the [usage guide](USAGE_GUIDE.md) for installation, signing in,
search filters, thumbnail timeline, Quick view, asset loading and commercial ordering.

## Installation

The plugin uses libraries supplied with QGIS and requires no additional Python packages or helper plugins.

### From QGIS repository

1. Go to menu Plugins -> All
2. Search for `EODH`
3. Click Install Plugin

### Manual

1. Download archive for your platform from releases
2. Open QGIS
3. Go to menu Plugins -> Manage and Install Plugins...
4. Select `Install from ZIP...`
5. Select the downloaded archive
6. Click `Install Plugin`

### Version compatibility

This plugin requires Python 3.9+ in the QGIS environment.

The recommended QGIS version is always the latest LTR or QGIS 4.

Installation is allowed on QGIS 3.0.0 and newer. We actively test QGIS 3.44 LTR and QGIS 4; older versions are not actively supported.

On MacOS the plugin usually bundles it's own Python distribution which should be 3.9 or newer.

If you encounter installation issues, please first try upgrading QGIS to the latest LTR or QGIS 4.

Please note that we can't test all possible combinations of operating systems and their versions, QGIS versions and various packaging and versions of python.

## Usage

See the [usage guide](USAGE_GUIDE.md) for installation, signing in, searching for data, loading imagery, and commercial orders.

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

Run `make install` to install the development dependencies, then `make check` for linting, formatting, and type checks.

All tests use pytest, with plain assertions, parameterized cases, and shared fixtures:

- `uv run pytest` runs the fast unit tests in `tests/unit` without QGIS.
- `make test` runs those unit tests, then the complete suite in a QGIS 4 Docker container.
- `make test qgis-image=qgis/qgis:3.44-trixie` runs the same suite on QGIS 3 LTR. CI tests both versions and uploads coverage to Codecov and JUnit test results as artifacts.

To run the complete suite without Docker, use the Python interpreter supplied with QGIS, with `pytest` and `pytest-cov` installed:

```sh
python -m pytest tests --cov=eodh_qgis --cov-report=term-missing --cov-report=xml --junitxml=test-results.xml
```

Use `-k streaming` to select matching tests, or a node ID such as `tests/qgis/test_login.py::test_sign_out_clears_credentials` to run one test (list available IDs with `--collect-only -q`). Reports are written to `coverage.xml` and `test-results.xml`.

The integration tests in `tests/qgis` exercise the current plugin's real Qt widgets, plugin lifecycle, login, catalogue and workspace screens, map interaction, streaming and automatic fallback, and NetCDF loading. Fixtures create an isolated QGIS profile, clean up widgets and map layers after each test, and shut down QGIS normally. Service responses are mocked; COG range reads use a local HTTP server. Tests do not require EODH credentials or place commercial orders.
