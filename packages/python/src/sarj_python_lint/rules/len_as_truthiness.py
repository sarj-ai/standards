"""SARJ027: flag `len(x) <cmp> 0|1` comparisons that are just a truthiness test.

Six zero-boundary forms of `len(x)` compared against `0` or `1` are exactly
equivalent to testing the container's truthiness — an empty container is falsy,
a non-empty one is truthy:

    len(x) == 0   ->  not x
    len(x) < 1    ->  not x
    len(x) <= 0   ->  not x
    len(x) != 0   ->  x
    len(x) > 0    ->  x
    len(x) >= 1   ->  x

`len(x)` allocates nothing but reads as size arithmetic; the truthiness form is
shorter and states the intent. pylint shipped this as C1802/C1803 but neither
check was ever ported to ruff, so it is genuinely uncovered.

Deliberately NOT flagged — these are real size checks, not truthiness:
- exact-count / other-boundary comparisons (`len(x) == 1`, `>= 2`, `> 1`, `< 2`,
  `== 3`, ...); only the six zero-boundary forms above collapse to truthiness,
- a right-hand constant other than `0`/`1` (or a bool literal `True`/`False`),
- anything that is not literally `len(<one expr>)` on the left — a different
  builtin (`count(x) == 0`), `len` with 0/2+ args, or `len` called via attribute,
- chained comparisons (`0 < len(x) < 5`) — more than one operator,
- `x == []` / `x == {}` — a different check (it excludes `None`; see the
  separate empty-collection-literal rule).

The yoda form `0 == len(x)` is intentionally not handled (rare; would widen the
signal for little gain).

References:
- https://pylint.readthedocs.io/en/latest/user_guide/messages/refactor/use-implicit-booleaness-not-len.html
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule, parse_or_none


if TYPE_CHECKING:
    from pathlib import Path


# (comparison-operator type, right-hand int constant) pairs that are equivalent to a
# plain truthiness test, mapped to the truthy suggestion ("x") or falsy one ("not x").
_TRUTHINESS_FORMS: dict[tuple[type[ast.cmpop], int], str] = {
    (ast.Eq, 0): "not x",
    (ast.Lt, 1): "not x",
    (ast.LtE, 0): "not x",
    (ast.NotEq, 0): "x",
    (ast.Gt, 0): "x",
    (ast.GtE, 1): "x",
}


class LenAsTruthiness(Rule):
    """`len(x) <cmp> 0|1` zero-boundary comparisons — prefer a plain truthiness test."""

    id: str = "len-as-truthiness"
    code: str = "SARJ027"
    description: str = (
        "len(x) compared against 0/1 at a zero boundary is a truthiness test — "
        "use `x` / `not x` instead of `len(x)`."
    )

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        tree = parse_or_none(path, source)
        if tree is None:
            return []
        diags: list[Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            suggestion = _truthiness_suggestion(node)
            if suggestion is None:
                continue
            diags.append(
                Diagnostic(
                    path=path,
                    line=node.lineno,
                    col=node.col_offset + 1,
                    code=self.code,
                    message=(
                        f"len(...) compared against a zero boundary is a truthiness "
                        f"test — use `{suggestion}` instead of `len(...)`."
                    ),
                )
            )
        diags.sort(key=lambda d: (d.line, d.col))
        return diags


def _truthiness_suggestion(node: ast.Compare) -> str | None:
    """The `x`/`not x` suggestion if `node` is a zero-boundary `len(...)` compare, else None."""
    if len(node.ops) != 1 or len(node.comparators) != 1:
        return None
    if not _is_len_call(node.left):
        return None
    const = _int_constant(node.comparators[0])
    if const is None:
        return None
    return _TRUTHINESS_FORMS.get((type(node.ops[0]), const))


def _is_len_call(expr: ast.expr) -> bool:
    """True iff `expr` is literally `len(<single positional expr>)`."""
    if not isinstance(expr, ast.Call):
        return False
    if not (isinstance(expr.func, ast.Name) and expr.func.id == "len"):
        return False
    if len(expr.args) != 1 or expr.keywords:
        return False
    return not isinstance(expr.args[0], ast.Starred)


def _int_constant(expr: ast.expr) -> int | None:
    """The int value of a plain integer literal, else None. Bool literals are excluded."""
    if not isinstance(expr, ast.Constant):
        return None
    if type(expr.value) is not int:
        return None
    return expr.value
