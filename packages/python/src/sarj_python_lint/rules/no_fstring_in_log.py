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
    return is_logger_expr(func.value)


def _has_interpolation(node: ast.JoinedStr) -> bool:
    """True if the f-string actually interpolates a value (not just `f"literal"`)."""
    return any(isinstance(v, ast.FormattedValue) for v in node.values)
