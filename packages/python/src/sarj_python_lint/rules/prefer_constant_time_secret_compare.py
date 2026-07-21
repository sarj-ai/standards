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
from typing import TYPE_CHECKING, override

from sarj_python_lint._secret_names import is_secret_name
from sarj_python_lint.rule_base import Diagnostic, Rule, parse_or_none


if TYPE_CHECKING:
    from pathlib import Path


class PreferConstantTimeSecretCompare(Rule):
    """Direct `==`/`!=` on a secret-like value — prefer hmac.compare_digest."""

    id: str = "prefer-constant-time-secret-compare"
    code: str = "SARJ011"
    description: str = "Direct `==`/`!=` on a secret — prefer `hmac.compare_digest(a, b)`."

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        # Fixture equality assertions in tests (`result.api_key == "known"`) are
        # not a timing-attack surface — no attacker measures a test's clock.
        if _is_test_path(path):
            return []
        tree = parse_or_none(path, source)
        if tree is None:
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
            # Skip presence checks (None/True/False, numbers) and comparisons
            # against a compile-time str/bytes literal sentinel — an attacker
            # can't extract a runtime secret by timing a compare to a fixed
            # literal (ruff S105 covers hardcoded-secret literals separately).
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


def _is_test_path(path: Path) -> bool:
    return path.name.startswith("test_") or "tests" in path.parts


def _is_secret_operand(node: ast.AST) -> bool:
    """True if the operand's identifier names a secret."""
    if isinstance(node, ast.NamedExpr):
        node = node.target
    if isinstance(node, ast.Name):
        return is_secret_name(node.id)
    if isinstance(node, ast.Attribute):
        return is_secret_name(node.attr)
    return False


def _is_excluded_operand(node: ast.AST) -> bool:
    """True for operands that make the comparison a non-timing-attack surface.

    Covers `None`/`True`/`False`, numeric literals, and any str/bytes literal
    (a compile-time sentinel/placeholder, not a runtime secret to extract).
    """
    if isinstance(node, ast.Constant):
        value = node.value
        if value is None or isinstance(value, bool):
            return True
        if isinstance(value, (int, float, complex)):
            return True
        if isinstance(value, (str, bytes)):
            return True
    return False
