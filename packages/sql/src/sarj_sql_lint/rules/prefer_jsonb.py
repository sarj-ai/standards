"""SARJ106: forbid the non-B `JSON` type and `::json` casts — use JSONB.

Plain `json` stores raw text: every read re-parses, no indexing (GIN),
no containment operators, and duplicate keys / whitespace are preserved
so equality is unreliable. JSONB is the right default for every column
and cast; the word boundary in the pattern keeps `JSONB` itself, and
identifiers like `json_build_object`, from matching.
"""
from __future__ import annotations

import re
from pathlib import Path

from sarj_sql_lint.rule_base import Diagnostic, Rule


# \b...\b does not match JSONB (B is a word char) nor json_* identifiers
# (underscore is a word char), but catches both `JSON` column types and
# `::json` casts such as `DEFAULT '{}'::json`.
PATTERN = re.compile(r"\bJSON\b", re.IGNORECASE)


class PreferJsonb(Rule):
    """JSON column type or ::json cast — use JSONB."""

    id = "prefer-jsonb"
    code = "SARJ106"
    description = "JSON column type or ::json cast — use JSONB."

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
                            "Use JSONB — plain JSON has no indexing or containment "
                            "operators and re-parses on every read."
                        ),
                    )
                )
        return diags
