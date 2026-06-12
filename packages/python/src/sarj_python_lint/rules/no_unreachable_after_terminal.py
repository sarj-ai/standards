"""SARJ010: detect unreachable code after a terminal statement.

A terminal statement (`return`, `raise`, `break`, `continue`) ends control
flow for the enclosing block. Any statement that immediately follows it in the
same statement list can never execute — it is dead code, almost always a
logic error (e.g. a `return` placed before cleanup, or a stray statement after
a `break`).

This is a pure structural check: for every statement-list field on every node
(the `body`/`orelse`/`finalbody` lists of Module, FunctionDef, If, For, While,
With, Try, ExceptHandler, etc.), if a terminal appears before the last element
of that list, the statement immediately after it is unreachable.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

from sarj_python_lint.rule_base import Diagnostic, Rule

# Statements that terminate control flow for their enclosing block.
_TERMINALS = (ast.Return, ast.Raise, ast.Break, ast.Continue)

# Fields on AST nodes that hold a list of statements (a block body).
_BLOCK_FIELDS = ("body", "orelse", "finalbody")


class NoUnreachableAfterTerminal(Rule):
    """Code following a `return`/`raise`/`break`/`continue` is unreachable."""

    id = "no-unreachable-after-terminal"
    code = "SARJ010"
    description = (
        "Unreachable code after a terminal statement "
        "(`return`/`raise`/`break`/`continue`)."
    )

    def check(self, path: Path, source: str) -> list[Diagnostic]:
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return []
        diags: list[Diagnostic] = []
        for node in ast.walk(tree):
            for field in _BLOCK_FIELDS:
                raw = getattr(node, field, None)
                if not isinstance(raw, list):
                    continue
                # `getattr` is untyped; the block fields (`body`/`orelse`/
                # `finalbody`) only ever hold statements, so cast to a concrete
                # element type to keep the `.lineno`/`.col_offset` access below
                # well-typed under strict checking.
                stmts = cast("list[ast.stmt]", raw)
                # Find the first terminal that is not the last element; the
                # statement immediately after it is unreachable.
                for i in range(len(stmts) - 1):
                    if isinstance(stmts[i], _TERMINALS):
                        unreachable = stmts[i + 1]
                        diags.append(
                            Diagnostic(
                                path=path,
                                line=unreachable.lineno,
                                col=unreachable.col_offset + 1,
                                code=self.code,
                                message=(
                                    "Unreachable code — this statement follows a "
                                    "`return`/`raise`/`break`/`continue` and can "
                                    "never execute."
                                ),
                            )
                        )
                        break  # one diag per statement list (the first)
        return diags
