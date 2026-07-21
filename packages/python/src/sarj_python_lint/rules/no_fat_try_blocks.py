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
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule, parse_or_none


if TYPE_CHECKING:
    from pathlib import Path


_MAX_TRY_BODY_STATEMENTS = 3


def _can_raise(stmt: ast.stmt) -> bool:
    """True if the statement's subtree contains a call or `await` — i.e. it can
    plausibly raise. Pure assignments / rebinds with no call do not count."""
    return any(isinstance(n, (ast.Call, ast.Await)) for n in ast.walk(stmt))


def _all_handlers_reraise(handlers: list[ast.ExceptHandler]) -> bool:
    """True if every `except` handler's body ends in a `raise`. Such a `try` is
    doing uniform error-context/metric wrapping, not swallowing — its width is
    intentional. A handler that returns / continues / passes / logs-without-raise
    is swallowing and makes this False, so the block still fires."""
    return bool(handlers) and all(
        bool(h.body) and isinstance(h.body[-1], ast.Raise) for h in handlers
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
