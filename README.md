# sarj-ai/linting

Lint rules + maximally-strict configs for TypeScript + Python.

## How to use

| Tool | Add this |
|---|---|
| **ESLint** | `pnpm add -D @sarj/eslint-plugin` → `import sarj from "@sarj/eslint-plugin"; export default [...sarj.configs.recommended];` |
| **ruff** | `uv add --dev sarj-lint-configs` → `sarj-lint-configs sync --only ruff` → `[tool.ruff] extend = ".ruff-strict.toml"` |
| **pyright** | `sarj-lint-configs sync --only pyright` → in `pyrightconfig.json`: `{"extends": ".pyright-strict.toml"}` |
| **pre-commit (Python + SQL)** | `repo: https://github.com/sarj-ai/linting, rev: python-lint-v0.1.4` |

## Where things live

| Source | Published as |
|---|---|
| [`packages/eslint-plugin/`](packages/eslint-plugin/) | `@sarj/eslint-plugin` on [npm](https://www.npmjs.com/package/@sarj/eslint-plugin) |
| [`packages/python-lint/`](packages/python-lint/) | `sarj-python-lint` on [PyPI](https://pypi.org/project/sarj-python-lint/) |
| [`configs/`](configs/) | `sarj-lint-configs` on [PyPI](https://pypi.org/project/sarj-lint-configs/) (separate PR) |

## Release

One-step deploy. Tag and push — the `release.yml` workflow handles npm + PyPI publish in CI.

| Tag pattern | Publishes |
|---|---|
| `eslint-plugin-vX.Y.Z` | `@sarj/eslint-plugin` to npm |
| `python-lint-vX.Y.Z` | `sarj-python-lint` to PyPI |
| `lint-configs-vX.Y.Z` | `sarj-lint-configs` to PyPI |

```bash
git tag eslint-plugin-v1.2.0 && git push --tags
```

Local fallback: `NPM_TOKEN=... UV_PUBLISH_TOKEN=... make publish`.

Secrets needed in the repo: `NPM_TOKEN`, `PYPI_TOKEN_PYTHON_LINT`, `PYPI_TOKEN_LINT_CONFIGS`.

Each rule is self-documenting via its source file. MIT.
