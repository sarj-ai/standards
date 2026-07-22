"""SARJ002: detect O(n²) single-accumulator string growth inside loops.

Growing a string with `s += <str>` or `s = s + <str>` inside a loop is O(n²)
in CPython because strings are immutable — each step allocates a new string and
copies the previous one. Append to a list and `"".join(parts)` at the end for
O(n).

The rule fires only on genuine single-string accumulation. It deliberately does
NOT treat a `str()/repr()/format()` coercion, a `.join()` / `.format()` /
`.strftime()` call, or an `os.path.join(...)`-style call as accumulation — those
are either the prescribed remedy or a bounded per-iteration transform, not the
O(n²) defect. Per-slot writes (`parts[i] = ...`) and idempotent rebinding
(`x = f(x)`) are likewise excluded.

References:
- https://docs.python.org/3/library/stdtypes.html#str.join
- https://wiki.python.org/moin/PythonSpeed/PerformanceTips
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, TypeGuard, override

from sarj_python_lint.rule_base import Diagnostic, Rule, parse_or_none


if TYPE_CHECKING:
    from pathlib import Path


class InefficientStringConcatInLoop(Rule):
    """O(n²) string concatenation in a loop."""

    id: str = "inefficient-string-concat-in-loop"
    code: str = "SARJ002"
    description: str = "`s += '...'` / `s = s + '...'` in a loop is O(n²); append to a list and join."

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
                message="String concat in a loop is O(n²). Append to a list and `''.join(...)`.",
            )
            for node in visitor.hits
        ]


class _ConcatVisitor(ast.NodeVisitor):
    """Single O(n) pass flagging each in-loop string accumulation exactly once."""

    def __init__(self) -> None:
        self._loop_depth: int = 0
        self._string_vars: list[frozenset[str]] = [frozenset()]
        self.hits: list[ast.AugAssign | ast.Assign] = []

    @override
    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            saved_depth = self._loop_depth
            self._loop_depth = 0
            self._string_vars.append(_string_typed_locals(node))
            super().generic_visit(node)
            self._string_vars.pop()
            self._loop_depth = saved_depth
            return
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            self._loop_depth += 1
            super().generic_visit(node)
            self._loop_depth -= 1
            return
        if self._loop_depth and self._is_in_loop_concat(node):
            self.hits.append(node)
        super().generic_visit(node)

    def _is_in_loop_concat(self, node: ast.AST) -> TypeGuard[ast.AugAssign | ast.Assign]:
        if isinstance(node, ast.AugAssign):
            return isinstance(node.op, ast.Add) and self._is_string_growth(node.target, node.value)
        if isinstance(node, ast.Assign):
            return any(self._is_self_add_growth(target, node.value) for target in node.targets)
        return False

    def _is_self_add_growth(self, target: ast.expr, value: ast.expr) -> bool:
        """`s = s + <str>` — a BinOp(Add) rebinding the target to itself-plus-more."""
        if not isinstance(value, ast.BinOp) or not isinstance(value.op, ast.Add):
            return False
        other = _other_add_operand(target, value)
        if other is None:
            return False
        return self._is_string_growth(target, other)

    def _is_string_growth(self, target: ast.expr, rhs: ast.expr) -> bool:
        """True when appending `rhs` to `target` is single-string accumulation."""
        if isinstance(target, ast.Subscript):
            return False
        if _looks_like_string(rhs):
            return True
        if isinstance(rhs, ast.Name) and isinstance(target, ast.Name):
            return target.id in self._string_vars[-1]
        return False


def _other_add_operand(target: ast.expr, binop: ast.BinOp) -> ast.expr | None:
    """The non-target operand of `target + x` / `x + target`, or None if absent."""
    target_src = ast.unparse(target)
    if ast.unparse(binop.left) == target_src:
        return binop.right
    if ast.unparse(binop.right) == target_src:
        return binop.left
    return None


def _string_typed_locals(func: ast.AST) -> frozenset[str]:
    """Names assigned a string-literal-ish value in this function's own body.

    Used as the string-typed signal for bare-`Name` accumulation (`buf += line`):
    a numeric accumulator (`total = 0`) is absent, so `total += x` stays clean.
    """
    body = getattr(func, "body", None)
    if not isinstance(body, list):
        return frozenset()
    names: set[str] = set()
    for stmt in body:
        _collect_string_targets(stmt, names)
    return frozenset(names)


def _collect_string_targets(node: ast.AST, names: set[str]) -> None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
        return
    if isinstance(node, ast.Assign) and _looks_like_string(node.value):
        for target in node.targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    if (
        isinstance(node, ast.AnnAssign)
        and node.value is not None
        and isinstance(node.target, ast.Name)
        and _looks_like_string(node.value)
    ):
        names.add(node.target.id)
    for child in ast.iter_child_nodes(node):
        _collect_string_targets(child, names)


def _looks_like_string(node: ast.AST) -> bool:
    """Heuristic for 'this expression is obviously a string at runtime'.

    Deliberately conservative: a bare call (`str(x)`, `",".join(...)`,
    `os.path.join(...)`) is NOT treated as a string — those shapes also appear in
    benign one-shot reassignment and are not the accumulation defect.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return True
    if isinstance(node, ast.JoinedStr):  # f-string
        return True
    if isinstance(node, ast.NamedExpr):  # walrus `(y := <str>)`
        return _looks_like_string(node.value)
    if isinstance(node, ast.IfExp):  # ternary — string only if both branches are
        return _looks_like_string(node.body) and _looks_like_string(node.orelse)
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Add):
            return _looks_like_string(node.left) or _looks_like_string(node.right)
        if isinstance(node.op, ast.Mod):  # `"row %s" % x` — left operand decides
            return _looks_like_string(node.left)
    return False
