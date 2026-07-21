"""SARJ009: detect exception handlers that silently swallow via a sentinel return.

An `except` block whose final statement is `return <sentinel>` (None, False,
empty collection, empty string) and which never re-raises silently discards the
error. Callers then can't distinguish "no result" from "something broke", which
hides bugs and corrupts idempotency decisions.

Prefer re-raising, or returning a typed result (e.g. a Result/Optional that the
caller must explicitly handle).
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule, parse_or_none


if TYPE_CHECKING:
    from pathlib import Path


class NoSentinelReturnOnExcept(Rule):
    """Exception handler that swallows the error by returning a sentinel."""

    id: str = "no-sentinel-return-on-except"
    code: str = "SARJ009"
    description: str = "`except` handler returns a sentinel and never re-raises — the exception is silently swallowed."

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        tree = parse_or_none(path, source)
        if tree is None:
            return []
        diags: list[Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if not node.body:
                continue
            last = node.body[-1]
            if not isinstance(last, ast.Return):
                continue
            # Bare `return` (value is None) is semantically `return None` — a
            # sentinel. Only skip when there IS a value that isn't a sentinel.
            if last.value is not None and not _is_sentinel(last.value):
                continue
            if _handler_reraises(node):
                continue
            diags.append(
                Diagnostic(
                    path=path,
                    line=last.lineno,
                    col=last.col_offset + 1,
                    code=self.code,
                    message=(
                        "Exception is swallowed by returning a sentinel — "
                        "re-raise, or return a typed result and handle it "
                        "explicitly."
                    ),
                )
            )
        return diags


def _is_sentinel(value: ast.expr) -> bool:
    """True if `value` is a sentinel: None, False, empty collection/str, set()."""
    if isinstance(value, ast.Constant):
        # None, False, or empty string. Note: True / non-empty str / numbers
        # are meaningful and must not be flagged.
        if value.value is None or value.value is False:
            return True
        return isinstance(value.value, str) and not value.value
    # Empty list / dict / set / tuple literals.
    if isinstance(value, ast.List):
        return len(value.elts) == 0
    if isinstance(value, ast.Tuple):
        return len(value.elts) == 0
    if isinstance(value, ast.Set):
        # `set()` is a call, not a Set node; `{}` is a Dict. A Set node always
        # has at least one element, so it's never empty — but be explicit.
        return len(value.elts) == 0
    if isinstance(value, ast.Dict):
        return len(value.keys) == 0
    # `set()` call with no args.
    if isinstance(value, ast.Call):
        func = value.func
        return isinstance(func, ast.Name) and func.id == "set" and not value.args and not value.keywords
    return False


def _handler_reraises(handler: ast.ExceptHandler) -> bool:
    """True if the handler body contains a `raise`, ignoring nested functions.

    A `raise` inside a nested def/lambda doesn't re-raise for *this* handler, so
    we stop walking at function/lambda boundaries.
    """
    return any(_contains_raise(stmt) for stmt in handler.body)


def _contains_raise(node: ast.AST) -> bool:
    """Walk `node`, returning True on a `raise`, but not crossing nested defs."""
    # A `raise` inside a nested def/lambda doesn't re-raise for *this* handler,
    # so a node that IS a function/lambda contributes no re-raise.
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        return False
    if isinstance(node, ast.Raise):
        return True
    return any(_contains_raise(child) for child in ast.iter_child_nodes(node))
