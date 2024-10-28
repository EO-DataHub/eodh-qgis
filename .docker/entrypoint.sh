#!/bin/bash

set -e

pip3 install pyeodh pytest pytest-cov pytest-qgis

qgis_setup.sh

# Fix the symlink created by qgis_setup.sh
rm -rf  /root/.local/share/QGIS/QGIS3/profiles/default/python/plugins/eodh_qgis
ln -sf /tests_directory /root/.local/share/QGIS/QGIS3/profiles/default/python/plugins/eodh_qgis
ln -sf /tests_directory /usr/share/qgis/python/plugins/eodh_qgis

# Run supervisor
# This is the default command of qgis/qgis but we will run it in background
supervisord -c /etc/supervisor/supervisord.conf &

# Wait for XVFB
sleep 10

exec "$@"