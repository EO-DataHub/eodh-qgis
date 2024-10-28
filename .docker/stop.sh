#!/bin/bash

docker compose exec -T qgis rm -rf .pytest_cache
docker compose kill
docker compose rm -f
rm -rf dist