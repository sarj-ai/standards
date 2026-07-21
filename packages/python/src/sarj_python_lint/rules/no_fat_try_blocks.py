"""SARJ007: `try` block with more than 3 top-level statements that can raise.

A fat `try` body obscures which statement is actually expected to raise and
widens the blast radius of the `except` handlers: unrelated failures get
caught (and often swallowed or mis-reported) by handlers written for a
different operation. Keep the `try` skinny — isolate the throwing
statement(s) and move the non-throwing setup and follow-up work outside.

Two refinements keep the count aligned with that intent and avoid the
false-positive patterns that dominated real-world suppressions:

* Only top-level statements that *can raise* are counted — a statement counts
  toward the limit only if its subtree contains a call or `await`. Pure
  assignments / name-rebinds (`self.x = y`, `a = b.c`) don't obscure a throwing
  statement and are free. Statements nested inside an `if` / `with` / loop
  count as the single compound statement that contains them. Nested `try`
  blocks are checked independently. `try*` (PEP 654) is held to the same limit.
* `try` blocks that carry an `else` or `finally` clause are exempt. Those
  clauses are a deliberate success/cleanup contract that couples the body to
  the handler (a `finally` that tears down a resource, an `else`/`finally` that
  reads a status the body set) — statements can't be freely hoisted out without
  changing semantics, so the length check is counterproductive there.
* `try` blocks whose every `except` handler re-raises (bare `raise`, or
  `raise Wrapped from e`) are exempt. The fat-try smell is over-broad
  *swallowing*; when no handler swallows, the width is deliberate uniform
  error-context / metric wrapping and isolating one call would change which
  failures are reported. A handler that returns / continues / passes /
  logs-without-raise is swallowing and keeps the block in scope.

Instead of:
    try:
        payload = build_payload(order)
        response = client.send(payload)
        record = parse(response)
        store.save(record)
    except HTTPError:
        ...

Prefer:
    payload = build_payload(order)
    try:
        response = client.send(payload)
    except HTTPError:
        ...
    record = parse(response)
    store.save(record)

References:
- https://docs.python.org/3/tutorial/errors.html#handling-exceptions
- https://docs.python.org/3/library/ast.html#ast.Try
"""

from __future__ import annotations

import ast
import enum
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule, parse_or_none


if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


_MAX_TRY_BODY_STATEMENTS = 3

_NESTED_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def _walk_same_scope(node: ast.AST) -> Iterator[ast.AST]:
    """Like `ast.walk`, but does not descend into the *bodies* of nested
    `def` / `async def` / `lambda`. Those bodies do not run when the enclosing
    `try` executes, so calls inside them must not count as throwing. Decorators
    and default-argument expressions still run at definition time, so their
    fields are walked normally."""
    stack: list[ast.AST] = [node]
    while stack:
        current = stack.pop()
        yield current
        for field, value in ast.iter_fields(current):
            if isinstance(current, _NESTED_SCOPES) and field == "body":
                continue
            items = value if isinstance(value, list) else [value]
            stack.extend(item for item in items if isinstance(item, ast.AST))


def _can_raise(stmt: ast.stmt) -> bool:
    """True if the statement can plausibly raise when the `try` runs — i.e. its
    same-scope subtree contains a call or `await`. Pure assignments / rebinds and
    inert `def` / `lambda` definitions (whose bodies never execute here) are
    free."""
    return any(isinstance(n, (ast.Call, ast.Await)) for n in _walk_same_scope(stmt))


class _Exit(enum.Enum):
    RAISE = enum.auto()
    SWALLOW = enum.auto()
    FALL = enum.auto()


def _stmt_exits(stmt: ast.stmt) -> set[_Exit]:
    """The set of ways control can leave `stmt`: propagate an exception
    (`RAISE`), diverge without raising via return/break/continue (`SWALLOW`), or
    complete normally and fall through to the next statement (`FALL`)."""
    match stmt:
        case ast.Raise():
            return {_Exit.RAISE}
        case ast.Return() | ast.Break() | ast.Continue():
            return {_Exit.SWALLOW}
        case ast.If(body=body, orelse=orelse):
            else_exits = _body_exits(orelse) if orelse else {_Exit.FALL}
            return _body_exits(body) | else_exits
        case ast.With(body=body) | ast.AsyncWith(body=body):
            return _body_exits(body)
        case _:
            return {_Exit.FALL}


def _body_exits(stmts: list[ast.stmt]) -> set[_Exit]:
    exits: set[_Exit] = set()
    for stmt in stmts:
        stmt_exits = _stmt_exits(stmt)
        exits |= stmt_exits - {_Exit.FALL}
        if _Exit.FALL not in stmt_exits:
            return exits
    exits.add(_Exit.FALL)
    return exits


def _all_handlers_reraise(handlers: list[ast.ExceptHandler]) -> bool:
    """True if every `except` handler is guaranteed to re-raise on all paths —
    the block is uniform error-context/metric wrapping, not swallowing, so its
    width is intentional. A handler with any path that returns / continues /
    passes / falls through (including a conditional early return before a tail
    `raise`) is swallowing and makes this False, so the block still fires."""
    return bool(handlers) and all(
        _body_exits(h.body) == {_Exit.RAISE} for h in handlers
    )


class NoFatTryBlocks(Rule):
    """Try body with too many throwing statements — isolate the one that raises."""

    id: str = "no-fat-try-blocks"
    code: str = "SARJ007"
    description: str = "Try block has too many throwing statements — keep try blocks skinny."

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        tree = parse_or_none(path, source)
        if tree is None:
            return []
        diags: list[Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Try, ast.TryStar)):
                continue
            # An `else`/`finally` clause is a deliberate success/cleanup contract
            # that couples the body to the handler — don't fight it on length.
            if node.orelse or node.finalbody:
                continue
            # When every `except` re-raises, the wide body is a deliberate
            # error-context/metric wrapper, not an over-broad swallow — exempt.
            if _all_handlers_reraise(node.handlers):
                continue
            throwing = sum(_can_raise(stmt) for stmt in node.body)
            if throwing <= _MAX_TRY_BODY_STATEMENTS:
                continue
            diags.append(
                Diagnostic(
                    path=path,
                    line=node.lineno,
                    col=node.col_offset + 1,
                    code=self.code,
                    message=(
                        f"try block has {throwing} statements that can raise "
                        f"(max {_MAX_TRY_BODY_STATEMENTS}) — try blocks should "
                        "isolate the throwing statement(s); move non-throwing "
                        "work outside the try."
                    ),
                )
            )
        diags.sort(key=lambda d: (d.line, d.col))
        return diags
