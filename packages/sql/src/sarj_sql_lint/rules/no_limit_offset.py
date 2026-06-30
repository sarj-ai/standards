"""SARJ107: forbid `OFFSET` — use cursor-based pagination.

`LIMIT/OFFSET` scans and discards every skipped row, so page N costs O(N)
and deep pages time out as tables grow; rows also shift between pages when
data changes underneath. Use keyset/cursor pagination instead:
`WHERE id > :cursor ORDER BY id LIMIT n`.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, final, override

from sarj_sql_lint.rule_base import Diagnostic, Rule, mask_sql


if TYPE_CHECKING:
    from pathlib import Path


PATTERN = re.compile(r"\bOFFSET\b", re.IGNORECASE)


@final
class NoLimitOffset(Rule):
    """OFFSET keyword — use cursor pagination instead."""

    id = "no-limit-offset"
    code = "SARJ107"
    description = "OFFSET pagination — use cursor pagination (WHERE id > :cursor)."

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        diags: list[Diagnostic] = []
        for lineno, line in enumerate(mask_sql(source).splitlines(), start=1):
            diags.extend(
                Diagnostic(
                    path=path,
                    line=lineno,
                    col=match.start() + 1,
                    code=self.code,
                    message=(
                        "Use cursor pagination (WHERE id > :cursor ORDER BY id "
                        "LIMIT n) — OFFSET scans and discards every skipped row."
                    ),
                )
                for match in PATTERN.finditer(line)
            )
        return diags
