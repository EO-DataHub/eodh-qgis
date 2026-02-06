uv-run ?= uv run --no-sync

.PHONY: install
install:
	uv sync --frozen

.PHONY: update
update:
	uv sync

.PHONY: format
format:
	${uv-run} ruff check --fix
	${uv-run} ruff format

.PHONY: check
check:
	${uv-run} ruff check
	${uv-run} ruff format --check --diff
	${uv-run} pyright
	${uv-run} validate-pyproject pyproject.toml

.PHONY: typecheck
typecheck:
	${uv-run} pyright eodh_qgis

.PHONY: test
test:
	.docker/stop.sh
	.docker/start.sh
	sleep 5
	.docker/exec.sh

.git/hooks/pre-commit:
	${uv-run} pre-commit install
	curl -o .pre-commit-config.yaml https://raw.githubusercontent.com/EO-DataHub/github-actions/main/.pre-commit-config-python.yaml

.PHONY: setup
setup: update .git/hooks/pre-commit

.PHONY: pre-commit
pre-commit:
	${uv-run} pre-commit

.PHONY: pre-commit-all
pre-commit-all:
	${uv-run} pre-commit run --all-files
