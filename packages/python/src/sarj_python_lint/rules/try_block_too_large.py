"""SARJ009: detect `try` blocks that guard too many statements.

A large `try` block obscures which line is actually guarded and tends to
over-broaden exception handling: when many statements share one handler, an
exception from an unexpected statement gets silently caught by a handler that
was written for a different call. Narrowing the `try` to the single call that
can raise makes the handler's intent clear.
"""

from __future__ import annotations

import ast
from pathlib import Path

from sarj_python_lint.rule_base import Diagnostic, Rule


class TryBlockTooLarge(Rule):
    """A `try` block guarding more than `max_statements` top-level statements."""

    id = "try-block-too-large"
    code = "SARJ009"
    description = "`try` block guards too many statements — narrow it to the call that can raise."
    max_statements = 3

    def check(self, path: Path, source: str) -> list[Diagnostic]:
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return []
        diags: list[Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            count = len(node.body)
            if count > self.max_statements:
                diags.append(
                    Diagnostic(
                        path=path,
                        line=node.lineno,
                        col=node.col_offset + 1,
                        code=self.code,
                        message=(
                            f"the `try` guards {count} statements "
                            f"(> {self.max_statements}) — narrow it to the single "
                            "call that can raise so the handler's intent is clear."
                        ),
                    )
                )
        return diags
