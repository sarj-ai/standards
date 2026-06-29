"""SARJ020: no DISTINCT / GROUP BY / COUNT in a store query — aggregate elsewhere.

Heavy aggregation (`COUNT`, `GROUP BY`, `DISTINCT`) does not belong in the
transactional Postgres store layer: it scans, sorts, and hashes large row sets
on the primary, competing with the latency-critical OLTP path. The house
direction is to push aggregate/analytical reads to the columnar mirror
(ClickHouse / BigQuery), where they are cheap, and keep Postgres queries to
point lookups and small bounded reads.

This rule walks SQL string literals embedded in `.py` (`*_store.py`) and flags
any query (a string containing `FROM`) that uses `COUNT(`, `GROUP BY`, or
`DISTINCT`. `--` and `/* */` comments are stripped first.

    # flagged
    "SELECT status, COUNT(*) FROM call GROUP BY status"
    "SELECT DISTINCT org_id FROM call"

    # preferred
    point/bounded reads in Postgres; aggregate in ClickHouse/BigQuery.

If an aggregate genuinely must run on Postgres (e.g. a tiny bounded admin
count), suppress with `# sarj-noqa: SARJ020 — <reason>`.
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
# A real SQL query shape — not just the word "from", so prose/LLM-prompt strings
# (e.g. "distinct from unexpected exceptions") are not mistaken for queries.
_QUERY_SHAPE = re.compile(
    r"\bSELECT\b[\s\S]*?\bFROM\b|\bUPDATE\b[\s\S]*?\bSET\b|\bDELETE\b\s+FROM\b",
    re.IGNORECASE,
)

# ClickHouse IS the place for aggregation. A file that talks to ClickHouse (the
# columnar mirror) is exempt — only Postgres store queries are in scope.
_CLICKHOUSE_FILE = re.compile(
    r"\bclickhouse_connect\b|\bclickhouse_driver\b|^\s*import\s+clickhouse\b",
    re.MULTILINE,
)
# Belt-and-braces: a single query using ClickHouse-only functions is ClickHouse.
_CLICKHOUSE_SQL = re.compile(
    r"\barg(?:Max|Min)\b|\b_peerdb|\bJSONExtract|\buniqExact\b|\bgroupArray\b"
    r"|\barrayJoin\b|\bquantile\w*\(",
)

_AGGREGATIONS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("COUNT(", re.compile(r"\bCOUNT\s*\(", re.IGNORECASE)),
    ("GROUP BY", re.compile(r"\bGROUP\s+BY\b", re.IGNORECASE)),
    ("DISTINCT", re.compile(r"\bDISTINCT\b", re.IGNORECASE)),
)


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


class NoAggregationInStoreQuery(Rule):
    """DISTINCT / GROUP BY / COUNT in a store query — aggregate in ClickHouse."""

    id = "no-aggregation-in-store-query"
    code = "SARJ020"
    description = (
        "DISTINCT / GROUP BY / COUNT in a Postgres store query — push heavy "
        "aggregation to the columnar mirror (ClickHouse / BigQuery)."
    )

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        if _CLICKHOUSE_FILE.search(source):
            return []
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
            if _QUERY_SHAPE.search(sql) is None or _CLICKHOUSE_SQL.search(sql):
                continue
            found = [label for label, pat in _AGGREGATIONS if pat.search(sql)]
            if not found:
                continue

            diags.append(
                Diagnostic(
                    path=path,
                    line=node.lineno,
                    col=node.col_offset + 1,
                    code=self.code,
                    message=(
                        f"Store query uses {', '.join(found)} — push heavy "
                        "aggregation to ClickHouse / BigQuery, keep Postgres to "
                        "point/bounded reads. Suppress with `# sarj-noqa: SARJ020`."
                    ),
                )
            )
        diags.sort(key=lambda d: (d.line, d.col))
        return diags
