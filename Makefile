.PHONY: help build test publish-eslint publish-python-lint publish-lint-configs publish release

help:
	@echo "Targets:"
	@echo "  build                  Build all packages (npm pack + uv build)"
	@echo "  test                   Run all package tests"
	@echo "  publish-eslint         npm publish @sarj/eslint-plugin"
	@echo "  publish-python-lint    PyPI publish sarj-python-lint"
	@echo "  publish-lint-configs   PyPI publish sarj-lint-configs"
	@echo "  publish                All three publishes in sequence"
	@echo "  release                Bump versions, tag, push, publish (interactive)"

build:
	cd packages/eslint-plugin && npm pack --dry-run
	cd packages/python-lint   && uv build --wheel --sdist
	@if [ -d packages/lint-configs ]; then cd packages/lint-configs && uv build --wheel --sdist; fi

test:
	cd packages/eslint-plugin && npm test
	cd packages/python-lint   && uv run pytest -q
	@if [ -d packages/lint-configs ]; then cd packages/lint-configs && uv build --wheel >/dev/null && uv pip install --quiet --reinstall ./dist/*.whl && uv run --no-project pytest -q tests/; fi

publish-eslint:
	@test -n "$$NPM_TOKEN" || (echo "error: NPM_TOKEN unset"; exit 1)
	cd packages/eslint-plugin && npm publish --access public

publish-python-lint:
	@test -n "$$UV_PUBLISH_TOKEN" || (echo "error: UV_PUBLISH_TOKEN unset"; exit 1)
	cd packages/python-lint && uv build --wheel --sdist && uv publish

publish-lint-configs:
	@test -d packages/lint-configs || (echo "skip: packages/lint-configs/ not present on this branch"; exit 0)
	@test -n "$$UV_PUBLISH_TOKEN" || (echo "error: UV_PUBLISH_TOKEN unset"; exit 1)
	cd packages/lint-configs && uv build --wheel --sdist && uv publish

publish: publish-eslint publish-python-lint publish-lint-configs

release:
	@echo "Usage: tag the commit, then 'git push --tags' to trigger the release.yml workflow."
	@echo "Tag conventions:"
	@echo "  eslint-plugin-vX.Y.Z   -> publish @sarj/eslint-plugin"
	@echo "  python-lint-vX.Y.Z     -> publish sarj-python-lint"
	@echo "  lint-configs-vX.Y.Z    -> publish sarj-lint-configs"
