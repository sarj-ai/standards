"""SARJ007: `try` block whose body has more than 3 top-level statements.

A fat `try` body obscures which statement is actually expected to raise and
widens the blast radius of the `except` handlers: unrelated failures get
caught (and often swallowed or mis-reported) by handlers written for a
different operation. Keep the `try` skinny — isolate the throwing
statement(s) and move the non-throwing setup and follow-up work outside.

Only the top-level statements of the `try` body are counted; statements
nested inside an `if` / `with` / loop within the body count as the single
compound statement that contains them. Nested `try` blocks are checked
independently. `try*` (PEP 654 except-groups) is held to the same limit.

This is a direct Python port of the org's ESLint restriction
`TryStatement > BlockStatement[body.length > 3]` in eslint.strict.mjs.

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

from sarj_python_lint.rule_base import Diagnostic, Rule


if TYPE_CHECKING:
    from pathlib import Path


_MAX_TRY_BODY_STATEMENTS = 3


class NoFatTryBlocks(Rule):
    """Try body longer than 3 statements — isolate the throwing statement(s)."""

    id: str = "no-fat-try-blocks"
    code: str = "SARJ007"
    description: str = "Try block body exceeds 3 statements — keep try blocks skinny."

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return []
        diags: list[Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Try, ast.TryStar)):
                continue
            if len(node.body) <= _MAX_TRY_BODY_STATEMENTS:
                continue
            diags.append(
                Diagnostic(
                    path=path,
                    line=node.lineno,
                    col=node.col_offset + 1,
                    code=self.code,
                    message=(
                        f"try block has {len(node.body)} statements "
                        f"(max {_MAX_TRY_BODY_STATEMENTS}) — try blocks should "
                        "isolate the throwing statement(s); move non-throwing "
                        "work outside the try."
                    ),
                )
            )
        return diags
