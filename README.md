# sarj-ai/linting

Lint rules + maximally-strict configs for TypeScript + Python + SQL.

## How to use

| Tool | Add this |
|---|---|
| **ESLint** | `pnpm add -D @sarj/eslint-plugin` → use `packages/lint-configs/src/sarj_lint_configs/configs/eslint.strict.mjs` directly |
| **ruff** | `uv add --dev sarj-lint-configs` → `uv run sarj-lint-configs sync --only ruff` → `[tool.ruff] extend = ".ruff-strict.toml"` |
| **pyright** | `uv run sarj-lint-configs sync --only pyright` → in `pyrightconfig.json`: `{"extends": ".pyright-strict.toml"}` |
| **pre-commit (Python)** | `repo: https://github.com/sarj-ai/linting, rev: python-v0.2.0` |
| **pre-commit (SQL)** | `repo: https://github.com/sarj-ai/linting, rev: sql-v0.1.0` |

## Where things live

| Source | Published as |
|---|---|
| [`packages/typescript/`](packages/typescript/) | `@sarj/eslint-plugin` on [npm](https://www.npmjs.com/package/@sarj/eslint-plugin) |
| [`packages/python/`](packages/python/) | `sarj-python-lint` on [PyPI](https://pypi.org/project/sarj-python-lint/) |
| [`packages/sql/`](packages/sql/) | `sarj-sql-lint` on [PyPI](https://pypi.org/project/sarj-sql-lint/) |
| [`packages/lint-configs/`](packages/lint-configs/) | `sarj-lint-configs` on [PyPI](https://pypi.org/project/sarj-lint-configs/) |

## Release

Tag and push — the `release.yml` workflow handles publish via OIDC (PyPI) and `NPM_TOKEN` (npm).

| Tag pattern | Publishes |
|---|---|
| `typescript-vX.Y.Z` | `@sarj/eslint-plugin` to npm |
| `python-vX.Y.Z` | `sarj-python-lint` to PyPI |
| `sql-vX.Y.Z` | `sarj-sql-lint` to PyPI |
| `lint-configs-vX.Y.Z` | `sarj-lint-configs` to PyPI |

```bash
git tag python-v0.2.0 && git push --tags
```

Local fallback: `NPM_TOKEN=... make publish`.

Each rule is self-documenting via its source file. MIT.
