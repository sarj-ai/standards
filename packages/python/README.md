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
    - id: sarj-pydantic-at-boundaries
    - id: sarj-prefer-class-row
    - id: sarj-prefer-struct-over-namedtuple
    - id: sarj-no-comment-cruft
    - id: sarj-no-fstring-in-log
    - id: sarj-prefer-timedelta-for-durations  # see "baseline + warn" below
```

## CLI

```bash
sarj-python-lint check --rule no-sequential-await path/to/file.py
sarj-python-lint list-rules
```

Diagnostic format is `path:line:col: CODE message` — Ruff-compatible.

## Adopting a rule on an existing codebase (baseline + warn)

A new rule can light up hundreds of pre-existing violations. To roll one out
without a noisy big-bang fix, record the current violations as a **baseline** so
the rule only fails on *new* code:

```bash
# 1. one-time: snapshot existing violations (exits 0)
sarj-python-lint check --rule prefer-timedelta-for-durations \
  --write-baseline .sarj/timedelta-baseline.json $(git ls-files '*.py')

# 2. ongoing: existing violations are suppressed, new ones fail
sarj-python-lint check --rule prefer-timedelta-for-durations \
  --baseline .sarj/timedelta-baseline.json <files>
```

The baseline keys on `(path, code, message)` with a per-key count, so it
survives line moves and only the *added* occurrence fails. `--exit-zero` reports
violations but never fails CI (pure warn mode). In pre-commit, pass these through
`args:` — e.g. a warn-while-adopting hook:

```yaml
- id: sarj-prefer-timedelta-for-durations
  args: [--baseline, .sarj/timedelta-baseline.json]
```

Recommended split for this batch: ship `no-comment-cruft`,
`prefer-struct-over-namedtuple`, `no-fstring-in-log` as hard (blocking) hooks —
they have ~zero false positives — and adopt `prefer-timedelta-for-durations`
with a baseline (it flags ~100 legitimate-but-pre-existing durations).

## Suppression

Inline `# sarj-noqa: SARJ00X — <reason>` on the offending line.

Each rule's source under `src/sarj_python_lint/rules/` carries its own `description` and diagnostic message.
