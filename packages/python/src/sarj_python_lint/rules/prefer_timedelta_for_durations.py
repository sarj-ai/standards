"""SARJ014: flag a duration named in time units but typed as a raw `int`/`float`.

A parameter or field whose name carries a time unit (`timeout_seconds`,
`retry_interval_ms`, `ttl`, `backoff_minutes`, ...) but is annotated `int` or
`float` forces every call site to remember the unit and invites the
`_seconds` / `_ms` / `_minutes` naming-collision class of bugs. `datetime.timedelta`
makes the unit explicit at the call site and lets the type checker catch
mismatches.

    # flagged
    def schedule(self, timeout_seconds: int) -> None: ...
    class Settings(BaseModel):
        retry_interval_ms: float = 250.0

    # preferred
    def schedule(self, timeout: timedelta) -> None: ...
    class Settings(BaseModel):
        retry_interval: timedelta = timedelta(milliseconds=250)

Scope is deliberately narrow to keep false positives low: only annotated
function parameters and annotated assignments (`AnnAssign`, i.e. class/module
fields) are inspected, and only when the annotation is a bare `int`/`float`
(optionally `| None`). Plain local assignments are not flagged.

Deliberately NOT flagged:
- count-like names (`*_count`, `num_*`, `n_*`, `*_size`, `*_limit`, `retries`),
- calendar units that `timedelta` cannot express cleanly (`*_months`, `*_years`),
- absolute instants (`*_timestamp`, `*_epoch`, `expires_at`, `*_at`),
- anything already annotated `timedelta`.

Suppress an intentional raw-numeric duration with `# sarj-noqa: SARJ014 — <reason>`.

References:
- https://docs.python.org/3/library/datetime.html#timedelta-objects
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from sarj_python_lint.rule_base import Diagnostic, Rule

_UNIT_RE = re.compile(
    r"(?:^|_)(?:"
    r"seconds?|secs?|ms|millis|milliseconds?|"
    r"minutes?|mins?|hours?|hrs?|days?|"
    r"timeout|interval|ttl|delay|backoff|duration|cooldown|expires_in"
    r")(?:_|$)",
    re.IGNORECASE,
)

_EXCLUDE_RE = re.compile(
    r"(?:^|_)(?:count|num|n|size|len|length|limit|offset|index|idx|id|"
    r"version|month|months|year|years|timestamp|epoch)(?:_|$)|_at$|_ts$",
    re.IGNORECASE,
)


class PreferTimedeltaForDurations(Rule):
    """Duration named in time units but typed as a raw int/float — prefer timedelta."""

    id = "prefer-timedelta-for-durations"
    code = "SARJ014"
    description = (
        "Duration named in time units (timeout_seconds, ttl, ...) typed as raw "
        "int/float — use datetime.timedelta so the unit is explicit and checked."
    )

    def check(self, path: Path, source: str) -> list[Diagnostic]:
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return []
        diags: list[Diagnostic] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = node.args
                for a in (*args.posonlyargs, *args.args, *args.kwonlyargs):
                    self._consider(a.arg, a.annotation, a, diags, path)
            elif isinstance(node, ast.AnnAssign):
                name = _target_name(node.target)
                if name is not None:
                    self._consider(name, node.annotation, node, diags, path)
        return diags

    def _consider(
        self,
        name: str,
        annotation: ast.expr | None,
        node: ast.AST,
        diags: list[Diagnostic],
        path: Path,
    ) -> None:
        if annotation is None:
            return
        if not _UNIT_RE.search(name) or _EXCLUDE_RE.search(name):
            return
        numeric = _numeric_annotation(annotation)
        if numeric is None:
            return
        diags.append(
            Diagnostic(
                path=path,
                line=getattr(node, "lineno", 1),
                col=getattr(node, "col_offset", 0) + 1,
                code=self.code,
                message=(
                    f"`{name}: {numeric}` is a duration named in time units — use "
                    f"datetime.timedelta instead of a raw {numeric}."
                ),
            )
        )


def _target_name(target: ast.expr) -> str | None:
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return None


def _numeric_annotation(node: ast.expr) -> str | None:
    """Return 'int'/'float' if the annotation is int/float (optionally `| None`/Optional)."""
    name = _bare_numeric(node)
    if name is not None:
        return name
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        for side in (node.left, node.right):
            inner = _bare_numeric(side)
            if inner is not None:
                return inner
    if isinstance(node, ast.Subscript) and _is_optional(node.value):
        return _bare_numeric(node.slice)
    return None


def _bare_numeric(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name) and node.id in {"int", "float"}:
        return node.id
    return None


def _is_optional(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "Optional"
    if isinstance(node, ast.Attribute):
        return node.attr == "Optional"
    return False
