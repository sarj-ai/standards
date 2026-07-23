"""SARJ017: flag an f-string passed as the message to a logging call.

The house logging style is structured: pass variables as keyword arguments so
log aggregators can index and filter on them, and so the message template stays
constant across calls:

    # flagged
    logger.info(f"call {call_id} finished in {elapsed}s")

    # preferred
    logger.info("call finished", call_id=call_id, elapsed=elapsed)

F-string interpolation bakes the values into the message text, defeating
structured search, breaking template grouping, and (for loguru) evaluating the
string even when the level is disabled.

To keep false positives near zero we require BOTH a logger-like receiver
(`logger`/`log`/`logging`/`loguru` and common aliases) AND a logging method
name — an f-string passed to some unrelated `.info(...)` is not flagged. The
receiver chain is resolved, so builder/factory forms are still caught:
`logger.bind(...).info(...)`, `logger.opt(lazy=True).debug(...)`. Only the first
positional argument (the message) is inspected.

The structured-keyword advice is loguru-specific: stdlib `logging` treats
trailing positional args as %-format parameters and reserves `exc_info` /
`stack_info` / `extra` keywords, so rewriting a stdlib call to
`logger.info("msg", key=value)` would silently break it. We therefore suppress
calls that carry a stdlib tell — a `logging.getLogger(...)` factory anywhere in
the receiver chain, or an `exc_info` / `stack_info` / `extra` keyword — and keep
firing on the loguru-shaped calls the advice actually applies to.

Suppress an intentional case with `# sarj-noqa: SARJ017 — <reason>`.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule, parse_or_none
from sarj_python_lint.rules._logging import is_logger_expr


if TYPE_CHECKING:
    from pathlib import Path


_LOG_METHODS = frozenset(
    {
        "debug",
        "info",
        "warning",
        "warn",
        "error",
        "exception",
        "critical",
        "fatal",
        "trace",
        "success",
        "log",
    }
)

# Keyword arguments defined by stdlib `logging` (and never structured fields).
# Their presence marks the call as a stdlib logger, for which the loguru-style
# structured-keyword rewrite is wrong.
_STDLIB_ONLY_KWARGS = frozenset({"exc_info", "stack_info", "extra"})


class NoFstringInLog(Rule):
    """f-string passed as a logging message — use structured keyword arguments."""

    id: str = "no-fstring-in-log"
    code: str = "SARJ017"
    description: str = (
        "f-string message in a logging call — pass variables as structured "
        "keyword arguments so logs stay filterable and templates stay constant."
    )

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        tree = parse_or_none(path, source)
        if tree is None:
            return []
        diags: list[Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _is_logging_call(node):
                continue
            if not node.args:
                continue
            if _is_stdlib_logging_call(node):
                continue
            offending = _interpolating_fstring(node.args[0])
            if offending is not None:
                diags.append(
                    Diagnostic(
                        path=path,
                        line=offending.lineno,
                        col=offending.col_offset + 1,
                        code=self.code,
                        message=(
                            "f-string logging message — pass variables as keyword "
                            "arguments (logger.info('msg', key=value)) instead."
                        ),
                    )
                )
        return diags


def _is_logging_call(node: ast.Call) -> bool:
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr not in _LOG_METHODS:
        return False
    return is_logger_expr(func.value)


def _is_stdlib_logging_call(node: ast.Call) -> bool:
    """Report whether the call carries a stdlib-`logging` tell the loguru advice breaks.

    Either a stdlib-reserved keyword (`exc_info`/`stack_info`/`extra`) or a
    `logging.getLogger(...)` factory anywhere in the receiver chain marks the
    logger as stdlib, whose message API is %-style positional, not structured
    keywords — so the rule must stay silent to avoid recommending a broken fix.

    Returns:
        True when the call looks like a stdlib logging call.

    """
    if any(kw.arg in _STDLIB_ONLY_KWARGS for kw in node.keywords):
        return True
    func = node.func
    return isinstance(func, ast.Attribute) and _chain_has_getlogger(func.value)


def _chain_has_getlogger(expr: ast.expr) -> bool:
    node = expr
    while True:
        if isinstance(node, ast.Call):
            called = node.func
            if isinstance(called, ast.Attribute) and called.attr == "getLogger":
                return True
            if isinstance(called, ast.Name) and called.id == "getLogger":
                return True
            node = called
        elif isinstance(node, ast.Attribute):
            node = node.value
        else:
            return False


def _interpolating_fstring(node: ast.expr) -> ast.JoinedStr | None:
    """Find an interpolating f-string in `node`, descending `+`-concat operands.

    A concatenated message like `f"{x}" + "!"` wraps the f-string in a `BinOp`,
    so the interpolation is not the top-level node — walk the `Add` tree to find
    it while leaving interpolation-free f-strings unflagged.

    Returns:
        The interpolating f-string node, or None if none is present.

    """
    if isinstance(node, ast.JoinedStr):
        return node if _has_interpolation(node) else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _interpolating_fstring(node.left) or _interpolating_fstring(node.right)
    return None


def _has_interpolation(node: ast.JoinedStr) -> bool:
    """Report whether the f-string actually interpolates a value (not just `f"literal"`).

    Returns:
        True when the f-string contains a formatted value.

    """
    return any(isinstance(v, ast.FormattedValue) for v in node.values)
