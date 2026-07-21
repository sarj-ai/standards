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
    """Single O(n) pass flagging each in-loop string concat exactly once."""

    def __init__(self) -> None:
        self._loop_depth: int = 0
        self.hits: list[ast.AugAssign | ast.Assign] = []

    @override
    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            saved = self._loop_depth
            self._loop_depth = 0
            super().generic_visit(node)
            self._loop_depth = saved
            return
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            self._loop_depth += 1
            super().generic_visit(node)
            self._loop_depth -= 1
            return
        if self._loop_depth and self._is_in_loop_concat(node):
            self.hits.append(node)
        super().generic_visit(node)

    @staticmethod
    def _is_in_loop_concat(node: ast.AST) -> bool:
        if isinstance(node, ast.AugAssign):
            return isinstance(node.op, ast.Add) and _looks_like_string(node.value)
        if isinstance(node, ast.Assign):
            return _looks_like_string(node.value) and any(
                _target_referenced_in(target, node.value) for target in node.targets
            )
        return False


def _target_referenced_in(target: ast.expr, value: ast.expr) -> bool:
    """True when the assignment target is read on the RHS (self-accumulation)."""
    target_src = ast.unparse(target)
    return any(
        ast.unparse(sub) == target_src
        for sub in ast.walk(value)
        if isinstance(sub, (ast.Name, ast.Attribute, ast.Subscript))
    )


def _looks_like_string(node: ast.AST) -> bool:
    """Heuristic for 'this RHS is probably a string at runtime'."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return True
    if isinstance(node, ast.JoinedStr):  # f-string
        return True
    if isinstance(node, ast.NamedExpr):  # walrus `(y := <str>)`
        return _looks_like_string(node.value)
    if isinstance(node, ast.IfExp):  # ternary — string only if both branches are
        return _looks_like_string(node.body) and _looks_like_string(node.orelse)
    if isinstance(node, ast.Call):
        # str(...) / repr(...) / format / strftime — usually string
        if isinstance(node.func, ast.Name) and node.func.id in {"str", "repr", "format"}:
            return True
        if isinstance(node.func, ast.Attribute):
            return node.func.attr in {"format", "strftime", "join"}
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Add):
            # `+` propagates string-ness if either side is a string
            return _looks_like_string(node.left) or _looks_like_string(node.right)
        if isinstance(node.op, ast.Mod):  # `"row %s" % x` — left operand decides
            return _looks_like_string(node.left)
    return False
