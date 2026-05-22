# sarj-python-lint

Custom Python + SQL lint rules for hypermodern codebases. AST-based (Python stdlib `ast` for Python rules, [sqlfluff](https://sqlfluff.com) for SQL). Designed for pre-commit.

## Install

```bash
pip install sarj-python-lint
# or via uv:
uv tool install sarj-python-lint
```

## CLI

```bash
sarj-python-lint check --rule no-sequential-await path/to/file.py
sarj-python-lint check --rule enforce-timestamptz svcs/db/db/migrations/*.sql
sarj-python-lint list-rules
```

Diagnostic format is `path:line:col: CODE message` — Ruff-compatible for editor integrations that consume that grammar.

## Pre-commit usage

```yaml
- repo: https://github.com/sarj-ai/linting
  rev: python-lint-v0.1.4
  hooks:
    # Python AST
    - id: sarj-no-sequential-await
    - id: sarj-inefficient-string-concat-in-loop
    - id: sarj-prefer-discriminated-union
    - id: sarj-prefer-str-enum
    # SQL (sqlfluff-based)
    - id: sarj-enforce-timestamptz
      files: '^svcs/db/db/migrations/.*\.sql$'
    # SQL (pygrep — no python install needed)
    - id: sarj-ban-postgres-enums
      files: '^svcs/db/db/migrations/.*\.sql$'
    - id: sarj-ban-create-trigger
      files: '^svcs/db/db/migrations/.*\.sql$'
    - id: sarj-require-if-not-exists-on-create
      files: '^svcs/db/db/migrations/.*\.sql$'
    - id: sarj-prefer-text-over-varchar
      files: '^svcs/db/db/migrations/.*\.sql$'
```

## Rules

Each rule links to its own docs page with bad/good examples, rationale, and suppression syntax.

### Python (AST)

| Code | Rule | Description |
|---|---|---|
| `SARJ001` | [`no-sequential-await`](docs/rules/no-sequential-await.md) | `for x in xs: await f(x)` — prefer `asyncio.gather`. |
| `SARJ002` | [`inefficient-string-concat-in-loop`](docs/rules/inefficient-string-concat-in-loop.md) | `s += "..."` in a loop is O(n²); append to list + join. |
| `SARJ005` | [`prefer-discriminated-union`](docs/rules/prefer-discriminated-union.md) | `BaseModel` with `success: bool` + Optionals → `Union[Success, Failure]`. |
| `SARJ006` | [`prefer-str-enum`](docs/rules/prefer-str-enum.md) | Pydantic str field that looks like a closed set → `StrEnum` (`Literal[...]` also accepted). |

### SQL (Postgres migrations)

| Code / Hook | Rule | Description |
|---|---|---|
| `SARJ101` | [`sarj-enforce-timestamptz`](docs/rules/enforce-timestamptz.md) | `TIMESTAMP` columns missing `WITH TIME ZONE`. |
| (pygrep) | [`sarj-ban-postgres-enums`](docs/rules/ban-postgres-enums.md) | `CREATE TYPE … AS ENUM` — use TEXT + CHECK. |
| (pygrep) | [`sarj-ban-create-trigger`](docs/rules/ban-create-trigger.md) | `CREATE TRIGGER` — encode rules in application code. |
| (pygrep) | [`sarj-require-if-not-exists-on-create`](docs/rules/require-if-not-exists-on-create.md) | `CREATE TABLE` must use `IF NOT EXISTS`. |
| (pygrep) | [`sarj-prefer-text-over-varchar`](docs/rules/prefer-text-over-varchar.md) | `VARCHAR(n)` → `TEXT`. |

## Suppression syntax

For Python rules (SARJ001 / SARJ002 / SARJ005 / SARJ006): inline comment with the rule code AND a reason.

```py
async def f(xs):
    for x in xs:
        result = await call(x)  # sarj-noqa: SARJ001 — each iteration consumes the previous result's next_id
```

We deliberately do NOT use `# noqa:` — ruff's `RUF100`/`RUF102` strip unrecognized codes even with `lint.external` set, which would silently break our suppressions. The distinct `sarj-noqa:` prefix sidesteps ruff entirely.

For SQL rules (no inline comment support — SQL doesn't have a meaningful equivalent), exclude specific files in the consumer's `.pre-commit-config.yaml`:

```yaml
- id: sarj-enforce-timestamptz
  files: '^svcs/db/db/migrations/.*\.sql$'
  exclude: |
    (?x)^(
      svcs/db/db/migrations/20240101_legacy_timestamp_table\.sql$
    )
```

## Adding rules

Subclass `sarj_python_lint.rule_base.Rule`. Implement `check(path, source) -> list[Diagnostic]`. Register in `sarj_python_lint.rules.REGISTRY`. Add an entry to the root `.pre-commit-hooks.yaml`. Write a docs page in `docs/rules/<rule-name>.md` following the Bad / Good / More examples / When to suppress / References template. Add tests in `tests/rules/test_<rule>.py`.

## License

MIT.
