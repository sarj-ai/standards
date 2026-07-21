"""SARJ009: detect exception handlers that silently swallow via a sentinel return.

An `except` block whose final statement is `return <sentinel>` (None, False,
empty collection, empty string) and which never re-raises silently discards the
error. Callers then can't distinguish "no result" from "something broke", which
hides bugs and corrupts idempotency decisions.

Prefer re-raising, or returning a typed result (e.g. a Result/Optional that the
caller must explicitly handle).

A handler that logs the exception (`logger.*` / `log.*` / `logging.*`) before
returning the sentinel is exempt: the error is observable, so the sentinel is the
handled result the caller expects rather than a silent swallow. The rule's value
is catching *silent* swallows — a handler that returns a sentinel with no logging
still fires.
"""

from __future__ import annotations

import ast
import re
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
            if _handler_logs_before_return(node):
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
        diags.sort(key=lambda d: (d.line, d.col))
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


_LOG_METHODS: frozenset[str] = frozenset(
    {
        "debug",
        "info",
        "warning",
        "warn",
        "error",
        "exception",
        "critical",
        "fatal",
    }
)


def _handler_logs_before_return(handler: ast.ExceptHandler) -> bool:
    """True if some logging call can reach the handler's final sentinel return.

    The final `return` is the caller's handled result; a logging call exempts the
    swallow only when a control-flow path leads from that call to the sentinel
    return (the error is observable on the path that yields the sentinel). Logging
    that sits on a branch which diverts elsewhere — e.g. `if v: log(); return x` —
    never reaches the sentinel and does not exempt it. Nested def/lambda bodies
    are not entered, since their logging can't run inline.
    """
    _, logged_fallthrough = _list_props(handler.body[:-1])
    return logged_fallthrough


def _list_props(stmts: list[ast.stmt]) -> tuple[bool, bool]:
    """Fall-through reachability for a statement list, ignoring the exit target.

    Returns `(unlogged, logged)`: whether a path can fall off the end of the list
    (reach the statement that follows it) without having logged, and whether one
    can having logged. `False, False` means every path diverts (return/raise)
    before the end.
    """
    reach_unlogged = True
    reach_logged = False
    for stmt in stmts:
        stmt_unlogged, stmt_logged = _stmt_props(stmt)
        stmt_falls = stmt_unlogged or stmt_logged
        new_logged = (reach_logged and stmt_falls) or (reach_unlogged and stmt_logged)
        new_unlogged = reach_unlogged and stmt_unlogged
        reach_logged, reach_unlogged = new_logged, new_unlogged
        if not reach_logged and not reach_unlogged:
            break
    return reach_unlogged, reach_logged


def _stmt_props(stmt: ast.stmt) -> tuple[bool, bool]:
    """`(unlogged, logged)` fall-through reachability for one statement.

    A path 'falls through' if control can continue to the next statement; 'logged'
    means a logging call ran on that path. Nested def/lambda/class bodies are not
    entered — their logging cannot execute inline before the sentinel return.
    """
    match stmt:
        case ast.Return() | ast.Raise() | ast.Break() | ast.Continue():
            return False, False
        case ast.FunctionDef() | ast.AsyncFunctionDef() | ast.ClassDef():
            return True, False
        case ast.If():
            return _if_props(stmt)
        case ast.For() | ast.AsyncFor() | ast.While():
            return _loop_props(stmt)
        case ast.With() | ast.AsyncWith():
            return _list_props(stmt.body)
        case ast.Try() | ast.TryStar():
            return _try_props(stmt)
        case ast.Match():
            return _match_props(stmt)
        case _:
            logs = _contains_logging_call(stmt)
            return not logs, logs


def _if_props(node: ast.If) -> tuple[bool, bool]:
    body_unlogged, body_logged = _list_props(node.body)
    else_unlogged, else_logged = _list_props(node.orelse) if node.orelse else (True, False)
    if _contains_logging_call(node.test):
        return False, (body_unlogged or body_logged or else_unlogged or else_logged)
    return body_unlogged or else_unlogged, body_logged or else_logged


def _loop_props(node: ast.For | ast.AsyncFor | ast.While) -> tuple[bool, bool]:
    _, body_logged = _list_props(node.body)
    else_unlogged, else_logged = _list_props(node.orelse) if node.orelse else (True, False)
    return else_unlogged, body_logged or else_logged


def _try_props(node: ast.Try | ast.TryStar) -> tuple[bool, bool]:
    fall_unlogged, fall_logged = _list_props([*node.body, *node.orelse])
    for handler in node.handlers:
        handler_unlogged, handler_logged = _list_props(handler.body)
        fall_unlogged = fall_unlogged or handler_unlogged
        fall_logged = fall_logged or handler_logged
    if node.finalbody:
        final_unlogged, final_logged = _list_props(node.finalbody)
        if not final_unlogged and not final_logged:
            return False, False
        if final_logged and not final_unlogged:
            return False, fall_unlogged or fall_logged
        fall_logged = fall_logged or (final_logged and (fall_unlogged or fall_logged))
    return fall_unlogged, fall_logged


def _match_props(node: ast.Match) -> tuple[bool, bool]:
    any_unlogged = False
    any_logged = False
    exhaustive = False
    for case in node.cases:
        case_unlogged, case_logged = _list_props(case.body)
        any_unlogged = any_unlogged or case_unlogged
        any_logged = any_logged or case_logged
        if _is_irrefutable_case(case):
            exhaustive = True
    if not exhaustive:
        any_unlogged = True
    if _contains_logging_call(node.subject):
        return False, (any_unlogged or any_logged)
    return any_unlogged, any_logged


def _is_irrefutable_case(case: ast.match_case) -> bool:
    """True for an unguarded `case _:` / `case name:` — always matches, so it makes
    the match exhaustive (no implicit unlogged fall-through past the match)."""
    return case.guard is None and isinstance(case.pattern, ast.MatchAs) and case.pattern.pattern is None


def _contains_logging_call(node: ast.AST) -> bool:
    """Walk `node` for a logging call, not crossing nested def/lambda boundaries."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        return False
    if _is_logging_call(node):
        return True
    return any(_contains_logging_call(child) for child in ast.iter_child_nodes(node))


_LOGGER_NAME_RE = re.compile(r"(?:^|_)(?:log|logger|logging)$")
_GETLOGGER_FUNCS: frozenset[str] = frozenset({"getLogger", "get_logger"})


def _is_logging_call(node: ast.AST) -> bool:
    """True for `<recv>.<level>(...)` where `<level>` is a standard logging method
    (`logger.warning`, `log.info`, `logging.error`) and `<recv>` is a logger.

    `print(...)` and bare reads of the exception are not logging.
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr not in _LOG_METHODS:
        return False
    return _is_logger_receiver(func.value)


def _is_logger_receiver(receiver: ast.expr) -> bool:
    """True if `receiver` denotes a logger: a name whose final word is
    `log`/`logger`/`logging` (`logger`, `_log`, `self.logger`, `app.log`), or an
    inline `getLogger(...)` / `get_logger(...)` call chain."""
    if isinstance(receiver, ast.Name):
        return _is_logger_name(receiver.id)
    if isinstance(receiver, ast.Attribute):
        return _is_logger_name(receiver.attr)
    if isinstance(receiver, ast.Call):
        return _is_getlogger_call(receiver)
    return False


def _is_logger_name(name: str) -> bool:
    """True when `log`/`logger`/`logging` is the whole name or its final
    underscore-delimited word — not a mere substring (`dialog`, `catalog`)."""
    return _LOGGER_NAME_RE.search(name) is not None


def _is_getlogger_call(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id in _GETLOGGER_FUNCS
    if isinstance(func, ast.Attribute):
        return func.attr in _GETLOGGER_FUNCS
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
