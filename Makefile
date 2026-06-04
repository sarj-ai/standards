SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
MAKEFLAGS += --warn-undefined-variables --no-builtin-rules

.PHONY: help build test typecheck publish publish-typescript publish-python publish-sql publish-lint-configs

help:
	@echo "Targets: build | test | typecheck | publish-{typescript,python,sql,lint-configs} | publish (all)"
	@echo "Releases trigger via tag push: typescript-v* python-v* sql-v* lint-configs-v*"

build:
	cd packages/typescript     && npm run build
	cd packages/python         && uv build --wheel --sdist
	cd packages/sql            && uv build --wheel --sdist
	cd packages/lint-configs   && uv build --wheel --sdist

test:
	cd packages/typescript     && npm test
	cd packages/python         && uv run pytest -q
	cd packages/sql            && uv run pytest -q
	cd packages/lint-configs   && uv build --wheel >/dev/null && uv pip install --quiet --reinstall ./dist/*.whl && uv run --no-project pytest -q tests/

typecheck:
	cd packages/python && uv run basedpyright src/
	cd packages/sql    && uv run basedpyright src/
	cd packages/typescript && npm run typecheck

publish-typescript:
	@test -n "$$NPM_TOKEN" || (echo "error: NPM_TOKEN unset"; exit 1)
	cd packages/typescript && npm publish --access public

publish-python:
	cd packages/python && uv build --wheel --sdist && uv publish

publish-sql:
	cd packages/sql && uv build --wheel --sdist && uv publish

publish-lint-configs:
	cd packages/lint-configs && uv build --wheel --sdist && uv publish

publish: publish-typescript publish-python publish-sql publish-lint-configs
