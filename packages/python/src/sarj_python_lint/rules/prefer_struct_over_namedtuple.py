"""SARJ015: flag `collections.namedtuple` — prefer `typing.NamedTuple` or a model.

`collections.namedtuple` produces an untyped, positionally-constructed tuple:
fields have no type annotations, the type checker can't catch a wrong-typed
field, and it silently supports tuple unpacking by position — the exact bug
class a named value object exists to prevent. `typing.NamedTuple` is the typed,
modern equivalent; a frozen pydantic `BaseModel` is better still when the value
crosses a boundary and needs validation.

    # flagged
    from collections import namedtuple
    Point = namedtuple("Point", ["x", "y"])
    Row = collections.namedtuple("Row", "id name")

    # preferred
    from typing import NamedTuple
    class Point(NamedTuple):
        x: float
        y: float

`typing.NamedTuple` is NOT flagged — it is the recommended form.

Suppress with `# sarj-noqa: SARJ015 — <reason>`.

References:
- https://docs.python.org/3/library/typing.html#typing.NamedTuple
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule, parse_or_none


if TYPE_CHECKING:
    from pathlib import Path


_MSG = (
    "collections.namedtuple is untyped and positionally constructed — prefer "
    "typing.NamedTuple, or a frozen pydantic BaseModel for boundary values."
)


class PreferStructOverNamedtuple(Rule):
    """`collections.namedtuple` — prefer typing.NamedTuple or a frozen model."""

    id: str = "prefer-struct-over-namedtuple"
    code: str = "SARJ015"
    description: str = (
        "collections.namedtuple is untyped/positional — prefer typing.NamedTuple or a frozen pydantic model."
    )

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        tree = parse_or_none(path, source)
        if tree is None:
            return []
        collections_names = _collections_bindings(tree)
        diags: list[Diagnostic] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "collections":
                diags.extend(self._diag(path, node) for alias in node.names if alias.name == "namedtuple")
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "namedtuple"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in collections_names
            ):
                diags.append(self._diag(path, node))
        return diags

    def _diag(self, path: Path, node: ast.AST) -> Diagnostic:
        return Diagnostic(
            path=path,
            line=getattr(node, "lineno", 1),
            col=getattr(node, "col_offset", 0) + 1,
            code=self.code,
            message=_MSG,
        )


def _collections_bindings(tree: ast.AST) -> set[str]:
    """Local names bound to the `collections` module, honouring `import ... as`."""
    names = {"collections"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "collections":
                    names.add(alias.asname or "collections")
    return names
