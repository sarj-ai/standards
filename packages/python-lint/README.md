# sarj-python-lint

Custom Python + SQL lint rules. Python via stdlib `ast`, SQL via [sqlfluff](https://sqlfluff.com) + pygrep. Designed for pre-commit.

```bash
uv tool install sarj-python-lint
```

## Pre-commit

```yaml
- repo: https://github.com/sarj-ai/linting
  rev: python-lint-v0.1.4
  hooks:
    - id: sarj-no-sequential-await
    - id: sarj-inefficient-string-concat-in-loop
    - id: sarj-prefer-discriminated-union
    - id: sarj-prefer-str-enum
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
sarj-python-lint check --rule no-sequential-await path/to/file.py
sarj-python-lint list-rules
```

Diagnostic format is `path:line:col: CODE message` — Ruff-compatible.

## Suppression

Inline `# sarj-noqa: SARJ00X — <reason>` on the offending line. (Not `# noqa:` — ruff strips unrecognized codes.) For SQL, exclude paths in the consumer's `.pre-commit-config.yaml`.

Each rule's source under `src/sarj_python_lint/rules/` carries its own `description` and diagnostic message — read the file for full rationale.
