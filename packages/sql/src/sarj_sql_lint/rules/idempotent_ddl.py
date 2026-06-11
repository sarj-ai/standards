"""SARJ102: DDL statements must be idempotent — migrations must be safe to re-run.

`CREATE TABLE` / `CREATE INDEX` / `ALTER TABLE ... ADD COLUMN` without
`IF NOT EXISTS`, or `DROP TABLE` / `DROP INDEX` without `IF EXISTS`, fail
the second time a migration runs. Re-runnable DDL means a half-applied or
replayed migration converges instead of crashing the deploy.
"""
from __future__ import annotations

import re
from pathlib import Path

from sarj_sql_lint.rule_base import Diagnostic, Rule


# `(?>\s+)` (atomic) stops the whitespace from backtracking past the negative
# lookahead, and `CONCURRENTLY` lives inside the lookahead for the same reason.
_CHECKS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\bCREATE\s+TABLE(?>\s+)(?!IF\s+NOT\s+EXISTS\b)", re.IGNORECASE),
        "`CREATE TABLE` without `IF NOT EXISTS` — migrations must be safe to re-run.",
    ),
    (
        re.compile(r"\bADD\s+COLUMN(?>\s+)(?!IF\s+NOT\s+EXISTS\b)", re.IGNORECASE),
        "`ADD COLUMN` without `IF NOT EXISTS` — migrations must be safe to re-run.",
    ),
    (
        re.compile(
            r"\bCREATE\s+(?:UNIQUE\s+)?INDEX(?>\s+)(?!(?:CONCURRENTLY\s+)?IF\s+NOT\s+EXISTS\b)",
            re.IGNORECASE,
        ),
        "`CREATE INDEX` without `IF NOT EXISTS` — migrations must be safe to re-run.",
    ),
    (
        re.compile(
            r"\bDROP\s+(?:TABLE|INDEX)(?>\s+)(?!(?:CONCURRENTLY\s+)?IF\s+EXISTS\b)",
            re.IGNORECASE,
        ),
        "`DROP TABLE`/`DROP INDEX` without `IF EXISTS` — migrations must be safe to re-run.",
    ),
)


class IdempotentDdl(Rule):
    """DDL without IF [NOT] EXISTS — migrations must be safe to re-run."""

    id = "idempotent-ddl"
    code = "SARJ102"
    description = "DDL without IF [NOT] EXISTS — migrations must be safe to re-run."

    def check(self, path: Path, source: str) -> list[Diagnostic]:
        diags: list[Diagnostic] = []
        for lineno, line in enumerate(source.splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith("--") or stripped.startswith("/*"):
                continue
            for pattern, message in _CHECKS:
                for match in pattern.finditer(line):
                    diags.append(
                        Diagnostic(
                            path=path,
                            line=lineno,
                            col=match.start() + 1,
                            code=self.code,
                            message=message,
                        )
                    )
        return diags
