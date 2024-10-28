# eodh-qgis Plugin

[![codecov](https://codecov.io/github/EO-DataHub/eodh-qgis/graph/badge.svg?token=N2VQBHVZN8)](https://codecov.io/github/EO-DataHub/eodh-qgis)

A QGIS plugin to integrate with the Earth Observation Data Hub (EODH)
This plugin demonstrates the EO Application Package and workflow capabilities of the EODH.

## Installation

### From QGIS repository

**_Note: This is not avaiable yet_**

1. Go to menu Plugins -> All
2. Search for `EODH Workflows`
3. Click Install Plugin

### Manual

1. Download archive for your platform from releases
2. Extract it to QGIS plugin directory.
   To find it go to QGIS menu Settings -> User profiles -> Open active profile folder -> python -> plugins
3. Make sure plugin is enabled in menu Plugins -> Manage and Install Plugin... -> Installed. There must be a tick next to EODH Workflows.

## Usage

When opening the plugin for the first time, you need to configure authentication credentials to access EODH APIs.

1. Click on settings button
2. Enter your EODH username and API token (can be generated in your account settings on EODH website).
3. Click back to Workflows or Jobs and your list will load normally.

## Development

### Requirements

Install pyeodh library to `libs/<os>` (os: `linux`, `darwin` or `windows`).

To e.g. install/update to latest version from pypi: `pip install --target libs/linux --upgrade pyeodh`

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
