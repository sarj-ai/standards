"""SARJ009: detect exception handlers that silently swallow via a sentinel return.

An `except` block whose final statement is `return <sentinel>` (None, False,
empty collection, empty string) and which never re-raises can silently discard the
error. Callers then can't distinguish "no result" from "something broke", which
hides bugs and corrupts idempotency decisions.

Prefer re-raising, or returning a typed result (e.g. a Result/Optional that the
caller must explicitly handle).

A handler that logs the exception (`logger.*` / `log.*` / `logging.*`) before
returning the sentinel is exempt: the error is observable, so the sentinel is the
handled result the caller expects rather than a silent swallow. The rule's value
is catching *silent* swallows — a handler that returns a sentinel with no logging
still fires.

Real-world sweeps (requests, httpx, FastAPI, Django) showed that a large share of
`except: return <sentinel>` sites are the function's *intended typed result*, not a
swallowed error. Four such shapes are exempt:

- **Predicate name:** the enclosing function is named like a boolean probe
  (`is_*` / `has_*` / `can_*` / `should_*`, plus `_`-prefixed forms) — e.g.
  `is_ipv4_address`, `_is_known_encoding`, `is_pydantic_v1_model`.
- **Boolean probe:** the handler returns `False`/`None` and a *non-exception* path
  of the same function returns a boolean — the classic `except: return False` /
  success `return True` predicate (e.g. `Response.ok`, `unicode_is_ascii`).
- **Feature detection / optional dependency:** the handler catches only
  `ImportError` / `ModuleNotFoundError` and returns a falsy sentinel — e.g.
  `is_pydantic_v1_model` (`except ImportError: return False`),
  `get_available_image_extensions` (`except ImportError: return []`).
- **Lookup-with-default:** the `try` body is a single `return <lookup>` guarded by a
  *narrow* exception (not bare `except:`, not `Exception`/`BaseException`) and the
  handler returns an empty sentinel — e.g. httpx `get_reason_phrase`
  (`try: return codes(value).phrase except ValueError: return ""`).

The genuine bug — a data-returning function whose success path yields real data and
whose broad handler swallows to a sentinel — still fires. A bare `except: pass`
that discards the error with no return is also flagged.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule, parse_or_none


if TYPE_CHECKING:
    from pathlib import Path


type ParentMap = dict[ast.AST, ast.AST]


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
        parents = _build_parent_map(tree)
        diags: list[Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            diag = self._check_handler(path, node, parents)
            if diag is not None:
                diags.append(diag)
        diags.sort(key=lambda d: (d.line, d.col))
        return diags

    def _check_handler(self, path: Path, handler: ast.ExceptHandler, parents: ParentMap) -> Diagnostic | None:
        if not handler.body:
            return None
        if _handler_reraises(handler):
            return None
        last = handler.body[-1]
        if isinstance(last, ast.Return) and (last.value is None or _is_sentinel(last.value)):
            if _handler_logs_before_return(handler):
                return None
            if _is_intended_result(handler, last, parents):
                return None
            return Diagnostic(
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
        if _is_bare_except_pass(handler):
            return Diagnostic(
                path=path,
                line=handler.lineno,
                col=handler.col_offset + 1,
                code=self.code,
                message=(
                    "Bare `except: pass` silently swallows the exception — "
                    "re-raise, log it, or handle it explicitly."
                ),
            )
        return None


def _build_parent_map(tree: ast.AST) -> ParentMap:
    parents: ParentMap = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _is_bare_except_pass(handler: ast.ExceptHandler) -> bool:
    """True for a bare `except:` whose body is nothing but `pass`.

    This discards the error with no observable trace and no returned result — the
    archetypal silent swallow. Typed handlers (`except ImportError: pass`) are left
    alone: `pass` there is often a deliberate optional-path no-op.
    """
    return handler.type is None and all(isinstance(stmt, ast.Pass) for stmt in handler.body)


def _is_intended_result(handler: ast.ExceptHandler, ret: ast.Return, parents: ParentMap) -> bool:
    """True when the handler's sentinel is the function's intended typed result.

    Covers predicate-named functions, boolean probes, optional-dependency feature
    detection, and lookup-with-default — the shapes real sweeps flagged as
    false positives. A broad handler in a data-returning function is not exempt.
    """
    exc_names = _handler_exc_names(handler)
    if _is_feature_detection(exc_names):
        return True
    func = _enclosing_function(handler, parents)
    if func is not None and _is_predicate_name(func.name):
        return True
    if _value_kind(ret.value) == "bool" and func is not None and _has_non_except_bool_return(func):
        return True
    return _is_lookup_with_default(handler, parents, exc_names)


def _handler_exc_names(handler: ast.ExceptHandler) -> tuple[str, ...] | None:
    """Simple names of the caught exception types, or None for a bare `except:` or
    an unrecognized (non-Name/Attribute) type expression."""
    caught = handler.type
    if caught is None:
        return None
    exprs = caught.elts if isinstance(caught, ast.Tuple) else [caught]
    names: list[str] = []
    for expr in exprs:
        if isinstance(expr, ast.Name):
            names.append(expr.id)
        elif isinstance(expr, ast.Attribute):
            names.append(expr.attr)
        else:
            return None
    return tuple(names)


_IMPORT_ERRORS: frozenset[str] = frozenset({"ImportError", "ModuleNotFoundError"})
_BROAD_ERRORS: frozenset[str] = frozenset({"Exception", "BaseException"})


def _is_feature_detection(exc_names: tuple[str, ...] | None) -> bool:
    """True when the handler catches only import errors — an optional-dependency
    fallback whose falsy return is the intended 'feature unavailable' result."""
    return exc_names is not None and len(exc_names) > 0 and all(name in _IMPORT_ERRORS for name in exc_names)


_PREDICATE_NAME_RE = re.compile(r"^_*(?:is|has|can|should)_")


def _is_predicate_name(name: str) -> bool:
    """True for boolean-probe names: `is_*`, `has_*`, `can_*`, `should_*`, and their
    underscore-prefixed forms (`_is_known_encoding`)."""
    return _PREDICATE_NAME_RE.match(name) is not None


def _enclosing_function(node: ast.AST, parents: ParentMap) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """The nearest enclosing function of `node`, or None at module level."""
    current = parents.get(node)
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current
        current = parents.get(current)
    return None


def _has_non_except_bool_return(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True if a non-exception path of `func` returns a boolean literal.

    Returns inside `except` handlers (the exception path) and inside nested
    functions/lambdas do not count — only the success path of THIS function.
    """
    return any(_value_kind(ret.value) == "bool" for stmt in func.body for ret in _non_except_returns(stmt))


def _non_except_returns(node: ast.AST) -> list[ast.Return]:
    """Return nodes reachable from `node` on a non-exception path: descend through
    ordinary statements but never into `except` handler bodies or nested
    function/lambda scopes."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        return []
    found: list[ast.Return] = []
    if isinstance(node, ast.Return):
        found.append(node)
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.ExceptHandler):
            continue
        found.extend(_non_except_returns(child))
    return found


def _is_lookup_with_default(handler: ast.ExceptHandler, parents: ParentMap, exc_names: tuple[str, ...] | None) -> bool:
    """True for the lookup-with-default idiom: a `try` body of exactly
    `return <lookup>` guarded by a narrow exception, with the handler supplying an
    empty default (`get_reason_phrase`: `try: return codes(v).phrase / except
    ValueError: return ""`).

    A bare `except:` or a broad `except Exception:` is NOT narrow — that is the
    swallow the rule exists to catch, so it still fires.
    """
    try_node = parents.get(handler)
    if not isinstance(try_node, ast.Try):
        return False
    if len(try_node.body) != 1:
        return False
    lookup = try_node.body[0]
    if not isinstance(lookup, ast.Return) or lookup.value is None or _is_sentinel(lookup.value):
        return False
    return exc_names is not None and not any(name in _BROAD_ERRORS for name in exc_names)


def _value_kind(value: ast.expr | None) -> str | None:
    """Coarse kind of a return value, used for boolean-probe matching. `None`
    (bare return or `None` literal) is "none"; `True`/`False` are "bool"."""
    if value is None:
        return "none"
    if isinstance(value, ast.Constant):
        raw = value.value
        if raw is None:
            return "none"
        if isinstance(raw, bool):
            return "bool"
    return None


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
