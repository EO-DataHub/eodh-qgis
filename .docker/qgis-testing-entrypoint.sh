#!/usr/bin/env bash

# Docker entrypoint file intended for docker-compose recipe for running unittests

set -e

pip3 install pyeodh coverage

qgis_setup.sh

# FIX default installation because the sources must be in "stream_feature_extractor" parent folder
rm -rf  /root/.local/share/QGIS/QGIS3/profiles/default/python/plugins/eodh_qgis
ln -sf /tests_directory /root/.local/share/QGIS/QGIS3/profiles/default/python/plugins/eodh_qgis
ln -sf /tests_directory /usr/share/qgis/python/plugins/eodh_qgis

# Run supervisor
# This is the default command of qgis/qgis but we will run it in background
supervisord -c /etc/supervisor/supervisord.conf &

# Wait for XVFB
sleep 10

exec "$@"