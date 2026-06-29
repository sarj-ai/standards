# sarj-ai/standards

The single home for Sarj code standards, in two layers:

- **Machine-enforced floor** — lint rules + maximally-strict configs for TypeScript + Python + SQL (`@sarj/eslint-plugin`, `sarj-python-lint`, `sarj-sql-lint`, `sarj-lint-configs`). Run in CI.
- **Judgment layer** — the `sarj-audit` Claude Code plugin: on-demand audit commands for the things that can't be reliably linted. Each audit cites the deterministic rule that backs it where one exists. (Merged here from the retired `sarj-ai/agentic` repo.)

## Claude Code plugin (`sarj-audit`)

This repo is a Claude Code plugin marketplace. Install the audit commands with:

```
/plugin marketplace add sarj-ai/standards
/plugin install sarj-audit@sarj
```

Then run any audit, e.g. `/sarj-audit:data-contracts` or `/sarj-audit:concurrency-and-performance`. The plugin lives in [`plugins/sarj-audit/`](plugins/sarj-audit/); [`commands/stack-detection.md`](plugins/sarj-audit/commands/stack-detection.md) is the shared stack-aware Phase-0 the audits gate on.

## How to use (lint rules)

| Tool | Add this |
|---|---|
| **ESLint** | `pnpm add -D @sarj/eslint-plugin` → use `packages/lint-configs/src/sarj_lint_configs/configs/eslint.strict.mjs` directly |
| **ruff** | `uv add --dev sarj-lint-configs` → `uv run sarj-lint-configs sync --only ruff` → `[tool.ruff] extend = ".ruff-strict.toml"` |
| **pyright** | `uv run sarj-lint-configs sync --only pyright` → in `pyrightconfig.json`: `{"extends": ".pyright-strict.json"}` |
| **pre-commit (Python)** | `repo: https://github.com/sarj-ai/standards, rev: python-v0.2.0` |
| **pre-commit (SQL)** | `repo: https://github.com/sarj-ai/standards, rev: sql-v0.1.0` |

## Where things live

| Source | Published as |
|---|---|
| [`packages/typescript/`](packages/typescript/) | `@sarj/eslint-plugin` on [npm](https://www.npmjs.com/package/@sarj/eslint-plugin) |
| [`packages/python/`](packages/python/) | `sarj-python-lint` on [PyPI](https://pypi.org/project/sarj-python-lint/) |
| [`packages/sql/`](packages/sql/) | `sarj-sql-lint` on [PyPI](https://pypi.org/project/sarj-sql-lint/) |
| [`packages/iac/`](packages/iac/) | `sarj-iac-lint` on [PyPI](https://pypi.org/project/sarj-iac-lint/) |
| [`packages/lint-configs/`](packages/lint-configs/) | `sarj-lint-configs` on [PyPI](https://pypi.org/project/sarj-lint-configs/) |
| [`plugins/sarj-audit/`](plugins/sarj-audit/) | `sarj-audit` Claude Code plugin (install via `/plugin marketplace add sarj-ai/standards`) |

## Release

Tag and push — the `release.yml` workflow handles publish via OIDC (PyPI) and `NPM_TOKEN` (npm).

| Tag pattern | Publishes |
|---|---|
| `typescript-vX.Y.Z` | `@sarj/eslint-plugin` to npm |
| `python-vX.Y.Z` | `sarj-python-lint` to PyPI |
| `sql-vX.Y.Z` | `sarj-sql-lint` to PyPI |
| `iac-vX.Y.Z` | `sarj-iac-lint` to PyPI |
| `lint-configs-vX.Y.Z` | `sarj-lint-configs` to PyPI |

```bash
git tag python-v0.2.0 && git push --tags
```

Local fallback: `NPM_TOKEN=... make publish`.

Each rule is self-documenting via its source file. MIT.
