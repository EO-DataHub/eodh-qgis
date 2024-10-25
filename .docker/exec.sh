#!/bin/bash

docker compose exec -T qgis qgis_testrunner.sh test_suite.test_package
