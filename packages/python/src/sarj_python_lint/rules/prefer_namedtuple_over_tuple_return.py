"""SARJ026: flag public functions returning a bare positional `tuple[A, B, ...]`.

A multi-field value returned across a boundary — from a public function (name not
starting `_`) — must be a `NamedTuple` (or a frozen pydantic model when it needs
validation), never a positional `tuple[A, B]` the caller has to unpack by position.
A bare `tuple[bytes, dict, str | None]` return forces every caller to remember which
slot is which; a typo swaps two fields silently. A named result gives each field a
name and lets pyright catch a wrong-order access.

    # flagged
    def download_to_memory(...) -> tuple[bytes, dict[str, str], str | None]:
        ...

    # preferred
    class Download(NamedTuple):
        body: bytes
        headers: dict[str, str]
        content_type: str | None

    def download_to_memory(...) -> Download:
        ...

The three tuple uses CLAUDE.md permits are deliberately NOT flagged:
- `tuple[X, ...]` — an immutable homogeneous sequence (Ellipsis form),
- `tuple[X, X]` — structurally homogeneous (every element identical, e.g.
  `tuple[int, int]`), a pair of the same thing rather than distinct fields,
- `tuple[Literal["both"], A, B]` — a discriminated-union tag (first element a
  `Literal[...]`).

Also NOT flagged: private (`_`-prefixed) functions, single-element `tuple[X]`,
a bare unsubscripted `tuple`, and any non-tuple / unannotated return.

Suppress a deliberate positional return with `# sarj-noqa: SARJ026 — <reason>`.

References:
- https://docs.python.org/3/library/typing.html#typing.NamedTuple

"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule, parse_or_none


if TYPE_CHECKING:
    from pathlib import Path


_TUPLE_NAMES = frozenset({"tuple", "Tuple"})
_LITERAL_NAMES = frozenset({"Literal"})

_MIN_ELEMENTS = 2

_MSG = (
    "public function returns a bare positional tuple[...] — callers must unpack by "
    "position; prefer a NamedTuple (or a frozen pydantic model for boundary values)."
)


class PreferNamedtupleOverTupleReturn(Rule):
    """Public function returning a bare positional `tuple[A, B, ...]` — prefer a NamedTuple."""

    id: str = "prefer-namedtuple-over-tuple-return"
    code: str = "SARJ026"
    description: str = (
        "public function returning a bare positional tuple[A, B, ...] — prefer a "
        "NamedTuple or frozen pydantic model so callers don't unpack by position."
    )

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        tree = parse_or_none(path, source)
        if tree is None:
            return []
        diags: list[Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_"):
                continue
            if node.returns is None:
                continue
            if not _is_bare_positional_tuple(node.returns):
                continue
            diags.append(
                Diagnostic(
                    path=path,
                    line=node.lineno,
                    col=node.col_offset + 1,
                    code=self.code,
                    message=_MSG,
                )
            )
        diags.sort(key=lambda d: (d.line, d.col))
        return diags


def _is_bare_positional_tuple(annotation: ast.expr) -> bool:
    """Report whether `annotation` is `tuple[A, B, ...]` with >=2 heterogeneous elements.

    Exempts the three permitted forms: `tuple[X, ...]` (Ellipsis), structurally
    homogeneous `tuple[X, X]`, and the `tuple[Literal[...], ...]` discriminated tag.

    Returns:
        True when the annotation is a bare positional heterogeneous tuple.

    """
    if not isinstance(annotation, ast.Subscript):
        return False
    if _name_of(annotation.value) not in _TUPLE_NAMES:
        return False
    if not isinstance(annotation.slice, ast.Tuple):
        return False
    elements = annotation.slice.elts
    if len(elements) < _MIN_ELEMENTS:
        return False
    if any(_is_ellipsis(el) for el in elements):
        return False
    if _all_equal(elements):
        return False
    return not _is_literal(elements[0])


def _all_equal(elements: list[ast.expr]) -> bool:
    """Report whether every element is structurally identical (a homogeneous pair/tuple).

    Returns:
        True when all elements are structurally equal.

    """
    first = elements[0]
    return all(_ast_equal(el, first) for el in elements[1:])


def _is_ellipsis(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is Ellipsis


def _is_literal(node: ast.expr) -> bool:
    """Report whether `node` is a `Literal[...]` subscript (discriminated-union tag).

    Returns:
        True when the node is a `Literal[...]` subscript.

    """
    return isinstance(node, ast.Subscript) and _name_of(node.value) in _LITERAL_NAMES


def _name_of(node: ast.expr) -> str | None:
    """Return the trailing name of a reference: `tuple` / `typing.Tuple` -> the trailing id.

    Returns:
        The trailing identifier, or None when `node` is neither a Name nor Attribute.

    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _ast_equal(a: ast.expr, b: ast.expr) -> bool:
    """Compare `a` and `b` structurally, ignoring source positions.

    Returns:
        True when the two trees are structurally equal.

    """
    return ast.dump(a) == ast.dump(b)
