"""SARJ101: detect TIMESTAMP columns missing `WITH TIME ZONE`.

Postgres `TIMESTAMP` without `WITH TIME ZONE` discards offset on INSERT,
silently producing wrong timestamps for non-UTC clients. Use TIMESTAMPTZ.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, final, override

from sarj_sql_lint.rule_base import Diagnostic, Rule, mask_sql


if TYPE_CHECKING:
    from pathlib import Path


# `\b...\b` already excludes TIMESTAMPTZ (no boundary before TZ). An optional
# precision modifier `(n)` is allowed before WITH TIME ZONE so the lookahead does
# not misfire on `TIMESTAMP(3) WITH TIME ZONE`.
PATTERN = re.compile(
    r"\bTIMESTAMP\b(?!\s*(?:\(\s*\d+\s*\)\s*)?WITH\s+TIME\s+ZONE\b)",
    re.IGNORECASE,
)


@final
class EnforceTimestamptz(Rule):
    """Postgres TIMESTAMP without WITH TIME ZONE — use TIMESTAMPTZ."""

    id = "enforce-timestamptz"
    code = "SARJ101"
    description = "TIMESTAMP without TIME ZONE — use TIMESTAMPTZ."

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
                        "Use `TIMESTAMPTZ` (or `TIMESTAMP WITH TIME ZONE`) — "
                        "naive TIMESTAMP discards offset and is rarely correct."
                    ),
                )
                for match in PATTERN.finditer(line)
            )
        return diags
