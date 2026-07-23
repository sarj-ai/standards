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
from itertools import pairwise
from typing import TYPE_CHECKING, override

from sarj_python_lint._secret_names import identifier_tokens, is_secret_name
from sarj_python_lint.rule_base import Diagnostic, Rule, parse_or_none


if TYPE_CHECKING:
    from pathlib import Path


# `is_secret_name` (shared with SARJ012) treats a hash/digest as secret material
# because logging one can still be sensitive. A timing-attack surface is narrower:
# only a MAC / authenticator whose bytes gate access. These extra SARJ011-only
# filters strip the classes that are secret-shaped by name but are not an auth
# comparison — so no_secret_in_log keeps its broader reach unchanged.

# Trailing token that makes the identifier metadata *about* a secret (its category
# / handle / label), not the credential: `token_type`, `token_name`, `session_id`,
# `credential_kind`. `type`/`id` are already dropped by the shared innocuous set;
# `name`/`kind` are added here because logging them can still matter (SARJ012) but
# they are never a timing surface.
_DESCRIPTOR_WORDS = frozenset({"type", "types", "name", "names", "id", "ids", "kind", "kinds"})

# A `type`/`kind` token anywhere marks an enum/category discriminator, not a
# credential: `TOKEN_TYPE_SYSTEM`, `credential_type`, `grant_kind`.
_CATEGORY_WORDS = frozenset({"type", "types", "kind", "kinds"})

# A leading boolean-predicate token marks a flag, not the credential itself:
# `is_token`, `has_secret`, `is_token_strategy`.
_FLAG_PREFIXES = frozenset({"is", "has", "was", "are", "can", "should"})

# Words that make an identifier a secret *only* via an integrity/content hash
# (`content_hash`, `metadata_hash`, `row_hash`) rather than an authenticator.
# A name that ALSO carries one of these keeps firing (`password_hash`,
# `token_hash`, `computed_hmac`, `signature`): those gate access, a plain digest
# of content does not.
_AUTH_WORDS = frozenset(
    {
        "token",
        "secret",
        "secrets",
        "password",
        "passwd",
        "passwords",
        "jwt",
        "credential",
        "credentials",
        "authorization",
        "signature",
        "hmac",
        "apikey",
    }
)


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
    """Report whether the operand's identifier names an auth secret worth constant-time compare.

    Returns:
        True when `node`'s identifier denotes an authenticator (not a category,
        integrity hash, or boolean flag that merely reads as secret-shaped).

    """
    if isinstance(node, ast.NamedExpr):
        node = node.target
    if isinstance(node, ast.Name):
        return _is_auth_secret_name(node.id)
    if isinstance(node, ast.Attribute):
        return _is_auth_secret_name(node.attr)
    return False


def _is_auth_secret_name(identifier: str) -> bool:
    """Report whether `identifier` names an authenticator (an access-gating secret).

    Narrows the shared `is_secret_name` for SARJ011: strips category/handle
    descriptors, `type`/`kind` discriminators, boolean flags, and integrity-only
    hashes, none of which are a timing-attack surface.

    Returns:
        True when comparing `identifier` in non-constant time leaks an auth secret.

    """
    if not is_secret_name(identifier):
        return False
    tokens = identifier_tokens(identifier)
    if tokens and tokens[0] in _FLAG_PREFIXES:
        return False
    if tokens and tokens[-1] in _DESCRIPTOR_WORDS:
        return False
    if any(tok in _CATEGORY_WORDS for tok in tokens):
        return False
    return _has_auth_word(tokens)


def _has_auth_word(tokens: list[str]) -> bool:
    """Report whether the identifier's secret-ness comes from an authenticator, not a bare hash.

    Returns:
        True when an auth word is present or `api` directly precedes `key`.

    """
    if any(tok in _AUTH_WORDS for tok in tokens):
        return True
    return any(a == "api" and b == "key" for a, b in pairwise(tokens))


def _is_excluded_operand(node: ast.AST) -> bool:
    """Report whether the operand makes the comparison a non-timing-attack surface.

    Covers `None`/`True`/`False`, numeric literals, any str/bytes literal, and an
    ALL-CAPS constant reference (`TOKEN_TYPE_SYSTEM`, `HTTP_DIGEST_AUTHENTICATION`,
    `PASSWORD_NOT_CHANGED`) — all compile-time sentinels/enum members, not a
    runtime secret an attacker can extract by timing the compare.

    Returns:
        True when `node` excludes the comparison from timing-attack concern.

    """
    if isinstance(node, ast.Constant):
        value = node.value
        if value is None or isinstance(value, bool):
            return True
        if isinstance(value, (int, float, complex)):
            return True
        if isinstance(value, (str, bytes)):
            return True
    if isinstance(node, ast.Name):
        return _is_constant_reference(node.id)
    if isinstance(node, ast.Attribute):
        return _is_constant_reference(node.attr)
    return False


def _is_constant_reference(identifier: str) -> bool:
    """Report whether `identifier` is an ALL-CAPS named constant (a compile-time sentinel).

    Returns:
        True when every cased character is upper-case and at least one letter exists.

    """
    return identifier.isupper() and any(c.isalpha() for c in identifier)
