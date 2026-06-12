"""SARJ105: `INSERT INTO` in a migration must carry an `ON CONFLICT` clause.

Migrations re-run: on replay, a bare INSERT either duplicates rows or
crashes on a unique constraint. Data writes in migrations must be
idempotent upserts (`INSERT ... ON CONFLICT ... DO UPDATE` / `DO NOTHING`).

Statements are delimited by `;` and may span multiple lines; `--` comments
are stripped before matching.
"""
from __future__ import annotations

import re
from pathlib import Path

from sarj_sql_lint.rule_base import Diagnostic, Rule


INSERT_PATTERN = re.compile(r"\bINSERT\s+INTO\b", re.IGNORECASE)
ON_CONFLICT_PATTERN = re.compile(r"\bON\s+CONFLICT\b", re.IGNORECASE)
_COMMENT_TAIL = re.compile(r"--.*$")


def _split_statements(source: str) -> list[list[tuple[int, str]]]:
    """Split source into statements: lists of (lineno, comment-stripped text).

    A statement ends at each `;`. Multiple statements on one line are split;
    statements may span many lines.
    """
    statements: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    for lineno, raw_line in enumerate(source.splitlines(), start=1):
        line = _COMMENT_TAIL.sub("", raw_line)
        while ";" in line:
            head, _, line = line.partition(";")
            current.append((lineno, head))
            statements.append(current)
            current = []
        if line:
            current.append((lineno, line))
    if current:
        statements.append(current)
    return statements


class InsertRequiresOnConflict(Rule):
    """INSERT INTO in a migration without ON CONFLICT — must be an idempotent upsert."""

    id = "insert-requires-on-conflict"
    code = "SARJ105"
    description = "INSERT without ON CONFLICT — migration data writes must be idempotent upserts."

    def check(self, path: Path, source: str) -> list[Diagnostic]:
        diags: list[Diagnostic] = []
        for statement in _split_statements(source):
            text = "\n".join(line for _, line in statement)
            if INSERT_PATTERN.search(text) is None or ON_CONFLICT_PATTERN.search(text):
                continue
            # Point at the line holding `INSERT INTO`; if the keywords are
            # split across lines, fall back to the statement's first line.
            lineno, col = statement[0][0], 1
            for stmt_lineno, line in statement:
                match = INSERT_PATTERN.search(line)
                if match:
                    lineno, col = stmt_lineno, match.start() + 1
                    break
            diags.append(
                Diagnostic(
                    path=path,
                    line=lineno,
                    col=col,
                    code=self.code,
                    message=(
                        "Data writes in migrations must be idempotent upserts — "
                        "add `ON CONFLICT ... DO UPDATE` (or `DO NOTHING`)."
                    ),
                )
            )
        return diags
