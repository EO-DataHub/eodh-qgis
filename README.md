# eodh-qgis Plugin

A QGIS plugin to integrate with the Earth Observation Data Hub (EODH)
This plugin demonstrates the EO Application Package and workflow capabilities of the EODH.

## Development

### Requirements

Install Plugin Builder Tool

`pip install --user pb_tool`

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

   `pbt deploy -y -p <path/to/plugins>`

3. Reload plugin
