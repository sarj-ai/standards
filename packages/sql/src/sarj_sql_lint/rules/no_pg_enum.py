"""SARJ103: forbid `CREATE TYPE ... AS ENUM` — use TEXT + CHECK constraint.

Postgres enums can't be altered transactionally: adding a value can't run
inside the same transaction that uses it, removing or reordering values is
effectively impossible, and renames ripple through every dependent object.
A TEXT column with a CHECK constraint gives the same integrity guarantee
and migrates with a plain `ALTER TABLE ... DROP/ADD CONSTRAINT`.
"""
from __future__ import annotations

import re
from pathlib import Path

from sarj_sql_lint.rule_base import Diagnostic, Rule


PATTERN = re.compile(r"\bCREATE\s+TYPE\b.*?\bAS\s+ENUM\b", re.IGNORECASE)


class NoPgEnum(Rule):
    """CREATE TYPE ... AS ENUM — use TEXT + CHECK constraint instead."""

    id = "no-pg-enum"
    code = "SARJ103"
    description = "CREATE TYPE ... AS ENUM — use TEXT + CHECK constraint instead."

    def check(self, path: Path, source: str) -> list[Diagnostic]:
        diags: list[Diagnostic] = []
        for lineno, line in enumerate(source.splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith("--") or stripped.startswith("/*"):
                continue
            for match in PATTERN.finditer(line):
                diags.append(
                    Diagnostic(
                        path=path,
                        line=lineno,
                        col=match.start() + 1,
                        code=self.code,
                        message=(
                            "Use TEXT + CHECK constraint — PG enums can't be "
                            "altered transactionally."
                        ),
                    )
                )
        return diags
