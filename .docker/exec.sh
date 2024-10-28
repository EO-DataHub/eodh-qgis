#!/bin/bash

docker compose exec -T qgis pytest -v --cov=./ --cov-report=xml
