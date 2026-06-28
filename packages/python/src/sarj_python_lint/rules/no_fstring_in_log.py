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
`logger.bind(...).info(...)`, `logger.opt(lazy=True).debug(...)`, and
`logging.getLogger(__name__).warning(...)`. Only the first positional argument
(the message) is inspected.

Suppress an intentional case with `# sarj-noqa: SARJ017 — <reason>`.
"""

from __future__ import annotations

import ast
from pathlib import Path

from sarj_python_lint.rule_base import Diagnostic, Rule

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

_LOGGER_NAMES = frozenset({"logger", "log", "logging", "loguru", "_logger", "_log"})

_LOGGER_FACTORIES = frozenset({"getlogger", "getchild"})


class NoFstringInLog(Rule):
    """f-string passed as a logging message — use structured keyword arguments."""

    id = "no-fstring-in-log"
    code = "SARJ017"
    description = (
        "f-string message in a logging call — pass variables as structured "
        "keyword arguments so logs stay filterable and templates stay constant."
    )

    def check(self, path: Path, source: str) -> list[Diagnostic]:
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return []
        diags: list[Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _is_logging_call(node):
                continue
            if not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.JoinedStr) and _has_interpolation(first):
                diags.append(
                    Diagnostic(
                        path=path,
                        line=getattr(first, "lineno", node.lineno),
                        col=getattr(first, "col_offset", node.col_offset) + 1,
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
    return _is_logger_expr(func.value)


def _is_logger_expr(expr: ast.expr) -> bool:
    """True if `expr` evaluates to a logger.

    Resolves the whole receiver chain so adapter/builder calls are caught:
    `logger.bind(...).info(...)`, `logger.opt(lazy=True).debug(...)`,
    `logging.getLogger(__name__).info(...)`, `self.logger.error(...)`.
    """
    if isinstance(expr, ast.Name):
        return expr.id.lower() in _LOGGER_NAMES
    if isinstance(expr, ast.Attribute):
        if expr.attr.lower() in _LOGGER_NAMES or expr.attr.lower() in _LOGGER_FACTORIES:
            return True
        return _is_logger_expr(expr.value)
    if isinstance(expr, ast.Call):
        if (
            isinstance(expr.func, ast.Attribute)
            and expr.func.attr.lower() in _LOGGER_FACTORIES
        ):
            return True
        return _is_logger_expr(expr.func)
    return False


def _has_interpolation(node: ast.JoinedStr) -> bool:
    """True if the f-string actually interpolates a value (not just `f"literal"`)."""
    return any(isinstance(v, ast.FormattedValue) for v in node.values)
