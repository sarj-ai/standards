"""SARJ021: no `SELECT *` in a store query — list the columns you need.

`SELECT *` over-fetches: it pulls every column (including large JSONB / text
blobs the caller never reads), breaks `class_row(Model)` mapping the moment a
column is added or reordered, and hides which columns a query actually depends
on. The recurring review ask is to name the columns explicitly.

This rule walks SQL string literals embedded in `.py` (`*_store.py`) and flags
any query (a string containing `FROM`) that selects `*` or `<alias>.*`. `--` and
`/* */` comments are stripped first. `COUNT(*)` is NOT flagged (the star is not a
projection), and `EXISTS (SELECT * ...)` is exempt (the columns are unused).

    # flagged
    "SELECT * FROM call WHERE id = %s"
    "SELECT c.* FROM call c"

    # preferred
    "SELECT id, status, created_at FROM call WHERE id = %s"

Suppress a deliberate case with `# sarj-noqa: SARJ021 — <reason>`.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule


if TYPE_CHECKING:
    from pathlib import Path


_LINE_COMMENT = re.compile(r"--.*?$", re.MULTILINE)
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
# A real SQL query shape, so prose strings with the bare word "from" aren't matched.
_QUERY_SHAPE = re.compile(r"\bSELECT\b[\s\S]*?\bFROM\b", re.IGNORECASE)
_SELECT_STAR = re.compile(
    r"\bSELECT\s+(?:ALL\s+|DISTINCT\s+)?(?:[A-Za-z_]\w*\.)?\*",
    re.IGNORECASE,
)
_EXISTS_BEFORE = re.compile(r"\bEXISTS\s*\(\s*$", re.IGNORECASE)


def _string_value(node: ast.expr) -> str | None:
    """Reconstruct a (possibly `+`-concatenated) string literal, else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _string_value(node.left)
        right = _string_value(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _strip_sql_comments(text: str) -> str:
    return _BLOCK_COMMENT.sub(" ", _LINE_COMMENT.sub("", text))


def _has_real_select_star(sql: str) -> bool:
    return any(_EXISTS_BEFORE.search(sql[: m.start()]) is None for m in _SELECT_STAR.finditer(sql))


class NoSelectStar(Rule):
    """`SELECT *` in a store query — list the columns explicitly."""

    id: str = "no-select-star"
    code: str = "SARJ021"
    description: str = (
        "SELECT * in a store query — name the columns; * over-fetches and breaks "
        "class_row mapping when the schema changes."
    )

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return []

        diags: list[Diagnostic] = []
        consumed: set[int] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant | ast.BinOp):
                continue
            if id(node) in consumed:
                continue
            text = _string_value(node)
            if text is None:
                continue
            consumed.update(id(sub) for sub in ast.walk(node))

            sql = _strip_sql_comments(text)
            if _QUERY_SHAPE.search(sql) is None or not _has_real_select_star(sql):
                continue

            diags.append(
                Diagnostic(
                    path=path,
                    line=node.lineno,
                    col=node.col_offset + 1,
                    code=self.code,
                    message=(
                        "Store query uses SELECT * — list the columns explicitly "
                        "(* over-fetches and breaks class_row mapping). Suppress "
                        "with `# sarj-noqa: SARJ021`."
                    ),
                )
            )
        diags.sort(key=lambda d: (d.line, d.col))
        return diags
