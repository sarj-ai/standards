"""SARJ104: forbid `VARCHAR(n)` / `CHARACTER VARYING(n)` — use TEXT.

In Postgres, VARCHAR(n) has no performance benefit over TEXT; the length
cap is a hidden business rule baked into the schema that fails with an
opaque error and needs a table rewrite-risking ALTER to change. Use TEXT,
and add an explicit CHECK (char_length(col) <= n) if a length limit is a
real domain constraint.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, final, override

from sarj_sql_lint.rule_base import Diagnostic, Rule, mask_sql


if TYPE_CHECKING:
    from pathlib import Path


PATTERN = re.compile(
    r"\b(?:VARCHAR|CHARACTER\s+VARYING)\s*\(",
    re.IGNORECASE,
)


@final
class PreferTextOverVarchar(Rule):
    """VARCHAR(n) / CHARACTER VARYING(n) — use TEXT (+ CHECK length if needed)."""

    id = "prefer-text-over-varchar"
    code = "SARJ104"
    description = "VARCHAR(n) — use TEXT (+ CHECK length if needed)."

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
                        "Use TEXT (+ CHECK length if needed) — VARCHAR(n) has "
                        "no benefit in Postgres and hides a business rule in DDL."
                    ),
                )
                for match in PATTERN.finditer(line)
            )
        return diags
