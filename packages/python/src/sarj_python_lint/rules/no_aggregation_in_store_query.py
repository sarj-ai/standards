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

Queries against the columnar mirrors are exempt: a file importing the ClickHouse
or BigQuery SDK, or a single query using ClickHouse-only functions or BigQuery
syntax (backtick-quoted table identifiers, BQ-only functions), is not a Postgres
store query and is out of scope.

If an aggregate genuinely must run on Postgres (e.g. a tiny bounded admin
count), suppress with `# sarj-noqa: SARJ020 — <reason>`.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule, parse_or_none


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

# BigQuery IS also a place for aggregation. Analytics/reporting services read the
# columnar BigQuery mirror, where COUNT / GROUP BY / DISTINCT are the whole point —
# only Postgres store queries are in scope. Mirror the ClickHouse exemption exactly:
# a file that imports the BigQuery SDK is exempt.
_BIGQUERY_FILE = re.compile(
    r"\bfrom\s+google\.cloud\s+import\s+bigquery\b"
    r"|\bfrom\s+google\.cloud\.bigquery\b"
    r"|\bimport\s+google\.cloud\.bigquery\b",
    re.MULTILINE,
)
# Belt-and-braces: a single query with a BigQuery-only signal is BigQuery. Backtick-
# quoted table identifiers (`project.dataset.table` / `{table}`) are BQ syntax — a
# Postgres/OLTP query never uses backticks — as are BQ-only functions. ARRAY_AGG /
# UNNEST / DATE_TRUNC are deliberately EXCLUDED: they exist in Postgres too, so they
# are not BigQuery signals.
_BIGQUERY_SQL = re.compile(
    r"\b(?:FROM|JOIN)\s+`"
    r"|\bAPPROX_COUNT_DISTINCT\s*\(|\bGENERATE_ARRAY\s*\(|\b_PARTITIONTIME\b"
    r"|\bSAFE_CAST\s*\(|\bPARSE_TIMESTAMP\s*\(|\bCOUNTIF\s*\(|\bSTRUCT\s*\(",
    re.IGNORECASE,
)

_AGGREGATIONS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("COUNT(", re.compile(r"\bCOUNT\s*\(", re.IGNORECASE)),
    ("GROUP BY", re.compile(r"\bGROUP\s+BY\b", re.IGNORECASE)),
    ("DISTINCT", re.compile(r"\bDISTINCT\b", re.IGNORECASE)),
)

# A diagnostic needs BOTH a query shape (SELECT/UPDATE/DELETE) and an aggregation
# (COUNT/GROUP/DISTINCT). Comment-stripping only ever deletes characters (or maps
# a `/* */` span to one space), so it can never introduce a contiguous keyword the
# raw literal lacks — a literal missing either substring class can never be
# flagged. Gate on two cheap linear scans before the expensive comment-strip and
# backtracking query-shape regex so large non-SQL prompt strings (which often
# contain "distinct"/"count"/"group" as prose but no query verb) are dismissed.
_VERB_GATE = re.compile(r"select|update|delete", re.IGNORECASE)
_AGG_GATE = re.compile(r"count|group|distinct", re.IGNORECASE)


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

    id: str = "no-aggregation-in-store-query"
    code: str = "SARJ020"
    description: str = (
        "DISTINCT / GROUP BY / COUNT in a Postgres store query — push heavy "
        "aggregation to the columnar mirror (ClickHouse / BigQuery)."
    )

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        # A diagnostic needs some string literal that carries both a query verb
        # and an aggregation keyword; `source` is a strict superset of every
        # literal, so if either class is absent from the whole file no diagnostic
        # is possible — skip the parse and full-tree walk entirely. Most files in
        # a store-lint sweep are not SQL-bearing, so this is the dominant win.
        if _AGG_GATE.search(source) is None or _VERB_GATE.search(source) is None:
            return []
        if _CLICKHOUSE_FILE.search(source) or _BIGQUERY_FILE.search(source):
            return []
        tree = parse_or_none(path, source)
        if tree is None:
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
            # Only a `+`-concatenated BinOp owns sub-nodes that the walk would
            # otherwise re-process; mark those consumed. A plain Constant has no
            # such descendants, and if it is itself a child of a string BinOp the
            # parent (visited first in this BFS walk) already consumed it — so the
            # per-Constant subtree walk is pure overhead on large literal-heavy
            # files (the dominant cost here).
            if isinstance(node, ast.BinOp):
                consumed.update(id(sub) for sub in ast.walk(node))

            if _AGG_GATE.search(text) is None or _VERB_GATE.search(text) is None:
                continue

            sql = _strip_sql_comments(text)
            if (
                _QUERY_SHAPE.search(sql) is None
                or _CLICKHOUSE_SQL.search(sql)
                or _BIGQUERY_SQL.search(sql)
            ):
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
