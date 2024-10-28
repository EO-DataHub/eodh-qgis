install:
	poetry install
check:
	poetry run black --preview --check eodh_qgis
	poetry run flake8 eodh_qgis
	poetry run isort --check --diff eodh_qgis
test:
	.docker/stop.sh
	.docker/start.sh
	sleep 5
	.docker/exec.sh
