#!/bin/bash

python3 deploy.py --dist dist/eodh_qgis
docker compose up -d --force-recreate --remove-orphans --build

