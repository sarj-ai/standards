"""SARJ018: embedded `INSERT INTO ... VALUES/SELECT` in store code must be an upsert.

Store write paths run under retries, races, and replays. A bare `INSERT`
either duplicates rows or crashes on a unique-constraint violation; the repo
standard is to make every store write an idempotent upsert
(`INSERT ... ON CONFLICT ... DO UPDATE` / `DO NOTHING`). This is the same rule
SARJ105 enforces for `.sql` migrations, applied to the raw SQL embedded in
`*_store.py` Python (the args to `cur.execute(...)`, `SQL("...")`, etc.).

This rule walks string literals (including `a + b` concatenations and adjacent
implicitly-concatenated literals, which Python already folds into one constant)
and flags any that contain a genuine `INSERT INTO ... VALUES` / `INSERT INTO
... SELECT` write with no `ON CONFLICT` clause. SQL string-literal values and
`--` / `/* */` comments are neutralized first, so an `ON CONFLICT` living inside
a quoted value never excuses a bare insert, a `--` inside a value never eats a
real clause, and commented-out keywords neither trigger nor excuse a finding.
Pure reads (`SELECT`), `RETURNING`-only tails, and statements that already carry
`ON CONFLICT` are left alone.

ClickHouse has no `ON CONFLICT`; for a genuine ClickHouse insert (or any other
deliberate non-upsert write) suppress with `# sarj-noqa: SARJ018 — <reason>`.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule, parse_or_none
from sarj_python_lint.rules._sql import sql_string_value, strip_sql_noise


if TYPE_CHECKING:
    from pathlib import Path


_INSERT_WRITE = re.compile(
    r"\bINSERT\s+INTO\b.*?\b(VALUES|SELECT|DEFAULT\s+VALUES)\b",
    re.IGNORECASE | re.DOTALL,
)
_ON_CONFLICT = re.compile(r"\bON\s+CONFLICT\b", re.IGNORECASE)


class StoreInsertRequiresOnConflict(Rule):
    """Embedded INSERT in store code without ON CONFLICT — store writes must be upserts."""

    id: str = "store-insert-requires-on-conflict"
    code: str = "SARJ018"
    description: str = (
        "Embedded SQL INSERT in store code without ON CONFLICT — store writes must be idempotent upserts."
    )

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
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
            text = sql_string_value(node)
            if text is None:
                continue
            consumed.update(id(sub) for sub in ast.walk(node))

            sql = strip_sql_noise(text)
            if _INSERT_WRITE.search(sql) is None or _ON_CONFLICT.search(sql):
                continue

            diags.append(
                Diagnostic(
                    path=path,
                    line=node.lineno,
                    col=node.col_offset + 1,
                    code=self.code,
                    message=(
                        "Store write must be an idempotent upsert — add "
                        "`ON CONFLICT ... DO UPDATE` (or `DO NOTHING`). "
                        "Suppress with `# sarj-noqa: SARJ018` for a deliberate "
                        "non-upsert write (e.g. ClickHouse)."
                    ),
                )
            )
        diags.sort(key=lambda d: (d.line, d.col))
        return diags
