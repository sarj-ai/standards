# sarj-sql-lint

Custom SQL lint rules for Postgres migrations. AST-based via [sqlfluff](https://sqlfluff.com) for the SARJ101 rule + zero-dependency pygrep regex hooks for migration-hygiene checks. Designed for pre-commit.

```bash
uv tool install sarj-sql-lint
```

## Pre-commit

```yaml
- repo: https://github.com/sarj-ai/standards
  rev: sql-v0.1.0
  hooks:
    - id: sarj-enforce-timestamptz
      files: '\.sql$'
    - id: sarj-ban-postgres-enums
      files: '\.sql$'
    - id: sarj-ban-create-trigger
      files: '\.sql$'
    - id: sarj-prefer-text-over-varchar
      files: '\.sql$'
```

## CLI

```bash
sarj-sql-lint check --rule enforce-timestamptz svcs/db/db/migrations/*.sql
sarj-sql-lint list-rules
```

Diagnostic format is `path:line:col: CODE message` — Ruff-compatible.

Each rule's source under `src/sarj_sql_lint/rules/` carries its own `description` and diagnostic message.
