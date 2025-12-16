install:
	poetry install


format:
	poetry run isort eodh_qgis
	poetry run black --preview eodh_qgis

check:
	poetry run black --preview --check eodh_qgis
	poetry run flake8 eodh_qgis
	poetry run isort --check --diff eodh_qgis
	poetry run pyright eodh_qgis

typecheck:
	poetry run pyright eodh_qgis

test:
	.docker/stop.sh
	.docker/start.sh
	sleep 5
	.docker/exec.sh
