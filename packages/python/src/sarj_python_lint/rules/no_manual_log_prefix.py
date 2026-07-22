"""SARJ029: flag a manual `"[Component] ..."` bracket tag in a logging message.

The house logging style is structured: identify the emitting component with a
bound field so aggregators can filter on it, rather than baking the label into
the message text where it can only be grepped:

    # flagged
    logger.info("[STT] transcription finished")

    # preferred
    logger.bind(component="STT").info("transcription finished")

A leading `[Tag]` in the literal message duplicates context that belongs in
structured metadata and fragments template grouping. This is distinct from
SARJ017 (no-fstring-in-log) / ruff G004, which fire only on *interpolating*
f-strings; the messages caught here are plain string literals.

To keep false positives near zero the rule requires BOTH a logger-like receiver
(resolved through builder/factory chains via `is_logger_expr`) AND a logging
method name, and only inspects the message argument (arg 1 for
`logger.log(LEVEL, msg)`, arg 0 otherwise).

The bracket tag must be a *component* label, not incidental data. The match
pattern allows only letters, spaces, underscores and hyphens inside the
brackets and requires at least one letter, so data-shaped brackets never match:
`[Errno 2]` (digit), `[1, 2]` (digit/comma), `['a', 'b']` (quotes/comma),
`[12:34]` (colon) are all excluded, while `[STT]`, `[TTS Pronunciation]` and
`[AgentDispatch]` match. Empirically this matches 0 data brackets across the
bulbul (273 hits) and noura (24 hits) corpora.

Suppress an intentional case with `# sarj-noqa: SARJ029 — <reason>`.
"""

from __future__ import annotations

import ast
import re
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

_PREFIX_RE = re.compile(r"^\[[A-Za-z_ -]*[A-Za-z][A-Za-z_ -]*\]")

_LOG_LEVEL_AND_MESSAGE_ARGC = 2


class NoManualLogPrefix(Rule):
    """Manual `[Component]` prefix in a logging message — bind it as structured context."""

    id: str = "no-manual-log-prefix"
    code: str = "SARJ029"
    description: str = (
        "manual '[Component]' prefix in a logging message — bind the component as "
        "structured context (logger.bind(component=...)) so aggregators filter on a "
        "field instead of grepping baked-in text."
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
            message = _message_arg(node)
            if message is None:
                continue
            leading = _leading_static_str(message)
            if leading is None or not _PREFIX_RE.match(leading):
                continue
            diags.append(
                Diagnostic(
                    path=path,
                    line=node.lineno,
                    col=node.col_offset + 1,
                    code=self.code,
                    message=(
                        "manual '[Component]' prefix in a logging message — bind it as "
                        "structured context (logger.bind(component=...)) instead."
                    ),
                )
            )
        diags.sort(key=lambda d: (d.line, d.col))
        return diags


def _is_logging_call(node: ast.Call) -> bool:
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr not in _LOG_METHODS:
        return False
    return is_logger_expr(func.value)


def _message_arg(node: ast.Call) -> ast.expr | None:
    """The message argument: index 1 for `logger.log(LEVEL, msg)`, else index 0.

    A `.log` call carrying fewer than two positionals has no message argument (the
    lone positional is the level), so there is nothing to inspect.
    """
    if isinstance(node.func, ast.Attribute) and node.func.attr == "log":
        return node.args[1] if len(node.args) >= _LOG_LEVEL_AND_MESSAGE_ARGC else None
    return node.args[0] if node.args else None


def _leading_static_str(node: ast.expr) -> str | None:
    """The leading static string of a message expr, or None if there isn't one.

    Handles a bare string literal, the leading literal chunk of an f-string, and
    the left operand of a `+`-concatenation (recursively), so a baked-in prefix
    is found even when the value is later interpolated or concatenated.
    """
    match node:
        case ast.Constant(value=str() as value):
            return value
        case ast.JoinedStr(values=[ast.Constant(value=str() as value), *_]):
            return value
        case ast.JoinedStr():
            return None
        case ast.BinOp(op=ast.Add(), left=left):
            return _leading_static_str(left)
        case _:
            return None
