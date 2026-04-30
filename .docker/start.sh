#!/bin/bash

python3 deploy.py --test dist/eodh_qgis
docker compose up -d --force-recreate --remove-orphans --build

