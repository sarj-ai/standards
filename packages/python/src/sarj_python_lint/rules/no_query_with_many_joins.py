"""SARJ019: a SQL query with 3+ JOINs is too entangled — split or denormalize.

Three years of store reviews repeatedly push back on multi-table joins inside a
single store query ("can we remove the joins?", "do the join at the application
layer", "whenever I see a join my ears perk up"). A query fanning across many
tables couples models that should stay separate, is hard to index well, and
usually wants either denormalization or splitting into per-store reads joined in
application code.

This rule walks SQL string literals embedded in `.py` (the raw queries in
`*_store.py`) and flags any single query string containing **3 or more** `JOIN`
keywords. `LEFT/RIGHT/INNER/FULL/CROSS JOIN` each count as one. `--` and
`/* */` SQL comments are stripped first. Only strings that actually look like a
query (they contain a `FROM`) are considered, keeping false positives low.

If a join-heavy read is genuinely the right call, suppress with
`# sarj-noqa: SARJ019 — <reason>`.
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
# A real query shape, so prose with the bare words "from"/"join" isn't matched.
_QUERY_SHAPE = re.compile(
    r"\bSELECT\b[\s\S]*?\bFROM\b|\bUPDATE\b[\s\S]*?\bSET\b|\bDELETE\b\s+FROM\b",
    re.IGNORECASE,
)
_JOIN = re.compile(r"\bJOIN\b", re.IGNORECASE)

_MAX_JOINS = 2


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


class NoQueryWithManyJoins(Rule):
    """A SQL query with 3+ JOINs is too entangled — split it or denormalize."""

    id = "no-query-with-many-joins"
    code = "SARJ019"
    description = (
        "SQL query with 3 or more JOINs — split the query or denormalize instead of fanning across many tables."
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
            if _QUERY_SHAPE.search(sql) is None:
                continue
            join_count = len(_JOIN.findall(sql))
            if join_count <= _MAX_JOINS:
                continue

            diags.append(
                Diagnostic(
                    path=path,
                    line=node.lineno,
                    col=node.col_offset + 1,
                    code=self.code,
                    message=(
                        f"Query has {join_count} JOINs (max {_MAX_JOINS}) — split it "
                        "into separate store reads joined in application code, or "
                        "denormalize. Suppress with `# sarj-noqa: SARJ019`."
                    ),
                )
            )
        diags.sort(key=lambda d: (d.line, d.col))
        return diags
