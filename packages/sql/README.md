# sarj-sql-lint

Custom SQL lint rules for Postgres migrations: zero-dependency pygrep regex hooks for migration-hygiene checks, designed for pre-commit. Migration-safety checks (timestamptz, concurrent index creation, TEXT-over-VARCHAR, robust/idempotent DDL) are delegated to [`squawk`](https://squawkhq.com), the real-parser Postgres migration linter run in pre-commit.

```bash
uv tool install sarj-sql-lint
```

## Rules

| Code    | id                            | Flags                                                                       |
| ------- | ----------------------------- | --------------------------------------------------------------------------- |
| SARJ103 | `no-pg-enum`                  | `CREATE TYPE ... AS ENUM` / `ALTER TYPE ... ADD VALUE` — use TEXT + CHECK constraint |
| SARJ105 | `insert-requires-on-conflict` | `INSERT INTO` statement (multi-line aware) with no `ON CONFLICT` clause      |
| SARJ106 | `prefer-jsonb`                | `JSON` column type or `::json` cast — use JSONB                              |
| SARJ107 | `no-limit-offset`             | `OFFSET` keyword — use cursor pagination (`WHERE id > :cursor ... LIMIT n`)  |

All scanning runs over a comment/string/dollar-quote-masked view of the source, so keywords inside `--`/`/* */` comments, `'...'` literals, `$tag$...$tag$` bodies and `"..."` identifiers never match.

## Suppression

Add a `-- sarj-noqa` comment on the offending line to silence a diagnostic; scope it to specific codes with `-- sarj-noqa: SARJ103, SARJ107`.

## Pre-commit

```yaml
- repo: https://github.com/sarj-ai/standards
  rev: sql-v0.1.0
  hooks:
    - id: sarj-enforce-timestamptz
      files: '\.sql$'
    - id: sarj-idempotent-ddl
      files: '\.sql$'
    - id: sarj-ban-postgres-enums
      files: '\.sql$'
    - id: sarj-ban-create-trigger
      files: '\.sql$'
    - id: sarj-prefer-text-over-varchar
      files: '\.sql$'
    - id: sarj-insert-requires-on-conflict
      files: '\.sql$'
    - id: sarj-prefer-jsonb
      files: '\.sql$'
    - id: sarj-no-limit-offset
      files: '\.sql$'
```

## CLI

```bash
sarj-sql-lint check --rule no-pg-enum svcs/db/db/migrations/*.sql
sarj-sql-lint list-rules
```

Diagnostic format is `path:line:col: CODE message` — Ruff-compatible.

Each rule's source under `src/sarj_sql_lint/rules/` carries its own `description` and diagnostic message.
