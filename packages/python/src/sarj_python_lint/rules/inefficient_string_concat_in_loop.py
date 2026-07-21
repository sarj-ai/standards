"""SARJ002: detect `s += "..."` inside loops.

String concatenation with `+=` inside a loop is O(n²) in CPython because
strings are immutable — each `+=` allocates a new string and copies the
previous one. Append to a list and `"".join(parts)` at the end for O(n).

References:
- https://docs.python.org/3/library/stdtypes.html#str.join
- https://wiki.python.org/moin/PythonSpeed/PerformanceTips
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule, parse_or_none


if TYPE_CHECKING:
    from pathlib import Path


class InefficientStringConcatInLoop(Rule):
    """O(n²) string concatenation in a loop."""

    id: str = "inefficient-string-concat-in-loop"
    code: str = "SARJ002"
    description: str = "`s += '...'` in a loop is O(n²); append to a list and join."

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        tree = parse_or_none(path, source)
        if tree is None:
            return []
        visitor = _ConcatVisitor()
        visitor.visit(tree)
        return [
            Diagnostic(
                path=path,
                line=node.lineno,
                col=node.col_offset + 1,
                code=self.code,
                message=("`+=` string concat in a loop is O(n²). Append to a list and `''.join(...)`."),
            )
            for node in visitor.hits
        ]


class _ConcatVisitor(ast.NodeVisitor):
    """Single O(n) pass flagging each in-loop string `+=` exactly once."""

    def __init__(self) -> None:
        self._loop_depth: int = 0
        self.hits: list[ast.AugAssign] = []

    @override
    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(node, (ast.For, ast.While)):
            self._loop_depth += 1
            super().generic_visit(node)
            self._loop_depth -= 1
            return
        if (
            self._loop_depth
            and isinstance(node, ast.AugAssign)
            and isinstance(node.op, ast.Add)
            and _looks_like_string(node.value)
        ):
            self.hits.append(node)
        super().generic_visit(node)


def _looks_like_string(node: ast.AST) -> bool:
    """Heuristic for 'this RHS is probably a string at runtime'."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return True
    if isinstance(node, ast.JoinedStr):  # f-string
        return True
    if isinstance(node, ast.Call):
        # str(...) / repr(...) / format / strftime — usually string
        if isinstance(node.func, ast.Name) and node.func.id in {"str", "repr", "format"}:
            return True
        if isinstance(node.func, ast.Attribute):
            return node.func.attr in {"format", "strftime", "join"}
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        # `+` propagates string-ness if either side is a string
        return _looks_like_string(node.left) or _looks_like_string(node.right)
    return False
