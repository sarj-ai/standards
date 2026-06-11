# sarj-sql-lint

Custom SQL lint rules for Postgres migrations. AST-based via [sqlfluff](https://sqlfluff.com) for the SARJ101 rule + zero-dependency pygrep regex hooks for migration-hygiene checks. Designed for pre-commit.

```bash
uv tool install sarj-sql-lint
```

## Rules

| Code    | id                            | Flags                                                                       |
| ------- | ----------------------------- | --------------------------------------------------------------------------- |
| SARJ101 | `enforce-timestamptz`         | `TIMESTAMP` without `WITH TIME ZONE` — use `TIMESTAMPTZ`                     |
| SARJ102 | `idempotent-ddl`              | `CREATE TABLE/INDEX`, `ADD COLUMN`, `DROP TABLE/INDEX` without `IF [NOT] EXISTS` |
| SARJ103 | `no-pg-enum`                  | `CREATE TYPE ... AS ENUM` — use TEXT + CHECK constraint                      |
| SARJ104 | `prefer-text-over-varchar`    | `VARCHAR(n)` / `CHARACTER VARYING(n)` — use TEXT (+ CHECK length if needed)  |
| SARJ105 | `insert-requires-on-conflict` | `INSERT INTO` statement (multi-line aware) with no `ON CONFLICT` clause      |
| SARJ106 | `prefer-jsonb`                | `JSON` column type or `::json` cast — use JSONB                              |
| SARJ107 | `no-limit-offset`             | `OFFSET` keyword — use cursor pagination (`WHERE id > :cursor ... LIMIT n`)  |

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
sarj-sql-lint check --rule enforce-timestamptz svcs/db/db/migrations/*.sql
sarj-sql-lint list-rules
```

Diagnostic format is `path:line:col: CODE message` — Ruff-compatible.

Each rule's source under `src/sarj_sql_lint/rules/` carries its own `description` and diagnostic message.
