"""SARJ011: detect `==`/`!=` comparisons on secret-like values.

Comparing secrets (tokens, signatures, HMACs, password hashes, API keys) with
`==`/`!=` is timing-attack-prone: short-circuiting on the first differing byte
leaks information about how many leading bytes matched. Use
`hmac.compare_digest(a, b)`, which compares in constant time.

References:
- https://docs.python.org/3/library/hmac.html#hmac.compare_digest
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from sarj_python_lint.rule_base import Diagnostic, Rule

# Identifiers that look like secrets. Matched against Name.id / Attribute.attr.
_SECRET_RE = re.compile(
    r"token|secret|signature|api_?key|hmac|digest|password|passwd|hash",
    re.IGNORECASE,
)


class PreferConstantTimeSecretCompare(Rule):
    """Direct `==`/`!=` on a secret-like value — prefer hmac.compare_digest."""

    id = "prefer-constant-time-secret-compare"
    code = "SARJ011"
    description = (
        "Direct `==`/`!=` on a secret — prefer `hmac.compare_digest(a, b)`."
    )

    def check(self, path: Path, source: str) -> list[Diagnostic]:
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return []
        diags: list[Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            # Only single-operator comparisons using == or != (Eq/NotEq).
            # Chained comparisons (a == b == c) and is/is not don't apply.
            if len(node.ops) != 1:
                continue
            if not isinstance(node.ops[0], (ast.Eq, ast.NotEq)):
                continue
            operands = [node.left, *node.comparators]
            # Skip presence checks: None/True/False, numbers, empty string "".
            if any(_is_excluded_operand(op) for op in operands):
                continue
            if not any(_is_secret_operand(op) for op in operands):
                continue
            diags.append(
                Diagnostic(
                    path=path,
                    line=node.lineno,
                    col=node.col_offset + 1,
                    code=self.code,
                    message=(
                        "Direct `==`/`!=` on a secret-like value is "
                        "timing-attack-prone — prefer "
                        "`hmac.compare_digest(a, b)`."
                    ),
                )
            )
        return diags


def _is_secret_operand(node: ast.AST) -> bool:
    """True if the operand's identifier matches the secret-name pattern."""
    if isinstance(node, ast.Name):
        return _SECRET_RE.search(node.id) is not None
    if isinstance(node, ast.Attribute):
        return _SECRET_RE.search(node.attr) is not None
    return False


def _is_excluded_operand(node: ast.AST) -> bool:
    """True for presence/identity-style operands we never want to flag.

    Covers `None`/`True`/`False`, numeric literals, and the empty string `""`.
    """
    if isinstance(node, ast.Constant):
        value = node.value
        if value is None or isinstance(value, bool):
            return True
        if isinstance(value, (int, float, complex)):
            return True
        if isinstance(value, str) and value == "":
            return True
    return False
