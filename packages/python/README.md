# sarj-python-lint

Custom Python lint rules via stdlib `ast`. Designed for pre-commit. For SQL rules see [`sarj-sql-lint`](../sql/).

```bash
uv tool install sarj-python-lint
```

## Pre-commit

```yaml
- repo: https://github.com/sarj-ai/standards
  rev: python-v0.2.0
  hooks:
    - id: sarj-no-sequential-await
    - id: sarj-inefficient-string-concat-in-loop
    - id: sarj-prefer-discriminated-union
    - id: sarj-prefer-str-enum
    - id: sarj-no-fat-try-blocks
```

## CLI

```bash
sarj-python-lint check --rule no-sequential-await path/to/file.py
sarj-python-lint list-rules
```

Diagnostic format is `path:line:col: CODE message` — Ruff-compatible.

## Suppression

Inline `# sarj-noqa: SARJ00X — <reason>` on the offending line.

Each rule's source under `src/sarj_python_lint/rules/` carries its own `description` and diagnostic message.
