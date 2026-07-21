from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from sarj_python_lint.rules.prefer_constant_time_secret_compare import (
    PreferConstantTimeSecretCompare,
)


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic


def _check(source: str) -> list[Diagnostic]:
    return PreferConstantTimeSecretCompare().check(Path("<test>.py"), source)


def _count(source: str) -> int:
    return len(_check(source))


# Every stem of the secret-name regex, exercised as a standalone identifier.
_SECRET_NAMES = [
    "token",
    "access_token",
    "refresh_token",
    "auth_token",
    "secret",
    "client_secret",
    "signature",
    "sig_signature",
    "apikey",
    "api_key",
    "hmac",
    "computed_hmac",
    "digest",
    "sha_digest",
    "password",
    "passwd",
    "hash",
    "password_hash",
]

_OPERATORS = ["==", "!="]


# ---------------------------------------------------------------------------
# Positive: a secret-like identifier compared with `==` / `!=`.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", _SECRET_NAMES)
@pytest.mark.parametrize("op", _OPERATORS)
def test_flags_secret_name_left_operand(name: str, op: str):
    src = f"def f({name}, other):\n    return {name} {op} other\n"
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ011"


@pytest.mark.parametrize("name", _SECRET_NAMES)
@pytest.mark.parametrize("op", _OPERATORS)
def test_flags_secret_name_right_operand_yoda(name: str, op: str):
    """Secret on the right-hand side (yoda-style) is flagged just the same."""
    src = f"def f({name}, other):\n    return other {op} {name}\n"
    assert _count(src) == 1


@pytest.mark.parametrize("op", _OPERATORS)
def test_flags_attribute_operand_left(op: str):
    src = f"def f(user, provided):\n    return user.password_hash {op} provided\n"
    assert _count(src) == 1


@pytest.mark.parametrize("op", _OPERATORS)
def test_flags_attribute_operand_right(op: str):
    src = f"def f(user, provided):\n    return provided {op} user.api_key\n"
    assert _count(src) == 1


def test_flags_nested_attribute_operand():
    src = "def f(req, expected):\n    return req.session.token == expected\n"
    assert _count(src) == 1


def test_flags_both_operands_secret_single_diagnostic():
    src = "def f(token, secret):\n    return token == secret\n"
    assert _count(src) == 1


def test_flags_secret_vs_runtime_operand():
    """Two runtime operands (secret vs another name) are a timing surface."""
    src = "def f(token, expected):\n    return token == expected\n"
    assert _count(src) == 1


def test_flags_comparison_inside_comprehension():
    src = "def f(items, token):\n    return [x for x in items if token == x]\n"
    assert _count(src) == 1


def test_flags_comparison_under_not():
    src = "def f(token, expected):\n    return not (token == expected)\n"
    assert _count(src) == 1


@pytest.mark.parametrize(
    "identifier",
    ["user_password_check", "the_signature_bytes", "x_hmac_y"],
)
def test_flags_secret_word_as_whole_token(identifier: str):
    """A secret word present as a whole snake/camel token is flagged."""
    src = f"def f({identifier}, other):\n    return {identifier} == other\n"
    assert _count(src) == 1


@pytest.mark.parametrize("identifier", ["subtoken", "mytokenvalue"])
def test_allows_secret_word_only_as_substring(identifier: str):
    """A secret word buried mid-word (not a whole token) is NOT a secret."""
    src = f"def f({identifier}, other):\n    return {identifier} == other\n"
    assert _check(src) == []


def test_message_mentions_compare_digest():
    diags = _check("def f(token, e):\n    return token == e\n")
    assert len(diags) == 1
    assert "compare_digest" in diags[0].message


# ---------------------------------------------------------------------------
# Negative: comparisons that must NOT be flagged.
# ---------------------------------------------------------------------------


def test_allows_compare_digest_hmac():
    src = "import hmac\n\ndef f(token, expected):\n    return hmac.compare_digest(token, expected)\n"
    assert _check(src) == []


def test_allows_compare_digest_secrets():
    src = "import secrets\n\ndef f(token, expected):\n    return secrets.compare_digest(token, expected)\n"
    assert _check(src) == []


@pytest.mark.parametrize(
    "identifier",
    ["name", "count", "index", "status", "email", "user_id", "value"],
)
def test_allows_non_secret_name(identifier: str):
    src = f'def f({identifier}):\n    return {identifier} == "admin"\n'
    assert _check(src) == []


def test_allows_two_non_secret_names():
    src = "def f(a, b):\n    return a == b\n"
    assert _check(src) == []


@pytest.mark.parametrize("op", ["is", "is not", "<", ">", "<=", ">=", "in", "not in"])
def test_allows_non_eq_operators(op: str):
    """Identity, ordering, and membership operators are out of scope."""
    src = f"def f(token, other):\n    return token {op} other\n"
    assert _check(src) == []


def test_allows_secret_in_assignment():
    src = "def f():\n    token = compute()\n    return token\n"
    assert _check(src) == []


def test_allows_secret_in_call_argument():
    src = "def f(token):\n    return log(token)\n"
    assert _check(src) == []


def test_allows_secret_in_binop():
    src = "def f(token, salt):\n    return token + salt\n"
    assert _check(src) == []


def test_allows_secret_subscript_operand():
    """Subscripts are out of scope — only Name.id / Attribute.attr are matched."""
    src = 'def f(headers, expected):\n    return headers["token"] == expected\n'
    assert _check(src) == []


# ---------------------------------------------------------------------------
# Excluded operands: presence / identity-style comparisons.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rhs",
    ["None", "True", "False", "0", "1", "0.0", "3.14", "1j", '""'],
)
@pytest.mark.parametrize("op", _OPERATORS)
def test_allows_secret_vs_excluded_operand(rhs: str, op: str):
    src = f"def f(token):\n    return token {op} {rhs}\n"
    assert _check(src) == []


@pytest.mark.parametrize("op", _OPERATORS)
def test_allows_excluded_operand_on_left(op: str):
    src = f"def f(token):\n    return None {op} token\n"
    assert _check(src) == []


def test_allows_secret_count_vs_zero():
    """`token_count == 0` is a count check — the numeric literal exempts it."""
    src = "def f(token_count):\n    return token_count == 0\n"
    assert _check(src) == []


# ---------------------------------------------------------------------------
# Literal-sentinel exemption: a secret compared to a compile-time str/bytes
# literal is a placeholder/state check, not a timing-attack surface.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("op", _OPERATORS)
@pytest.mark.parametrize(
    "literal",
    ['"PLACEHOLDER"', '"SENTINEL"', '"none"', "b'\\x00'", 'b"expected"', "'expected-value'"],
)
def test_allows_secret_vs_string_or_bytes_literal(op: str, literal: str):
    src = f"def f(password):\n    return password {op} {literal}\n"
    assert _check(src) == []


def test_allows_password_vs_placeholder_sentinel():
    """The real noura-be case: `password == "PLACEHOLDER"` is a sentinel check."""
    src = 'def f(password, password_confirmation):\n    return password == "PLACEHOLDER" or password_confirmation == "PLACEHOLDER"\n'
    assert _check(src) == []


def test_allows_token_vs_sentinel_literal():
    src = 'def f(token):\n    return token == "SENTINEL"\n'
    assert _check(src) == []


def test_allows_api_key_vs_bytes_literal():
    src = 'def f(api_key):\n    return api_key == b"\\x00\\x01"\n'
    assert _check(src) == []


def test_allows_secret_vs_string_literal_left_operand():
    src = 'def f(secret):\n    return "none" != secret\n'
    assert _check(src) == []


# ---------------------------------------------------------------------------
# Still fires: two runtime operands (Name/Attribute both sides).
# ---------------------------------------------------------------------------


def test_flags_two_runtime_hash_names():
    """`cached_hash != token_hash` compares two runtime secrets — still fires."""
    src = "def f(cached_hash, token_hash):\n    return cached_hash != token_hash\n"
    assert _count(src) == 1


def test_flags_secret_vs_stored_secret_name():
    src = "def f(password, stored_password):\n    return password == stored_password\n"
    assert _count(src) == 1


def test_flags_api_key_vs_request_key_name():
    src = "def f(api_key, req_key):\n    return api_key == req_key\n"
    assert _count(src) == 1


def test_flags_secret_vs_attribute_operand():
    src = "def f(secret, req):\n    return secret != req.stored_secret\n"
    assert _count(src) == 1


# ---------------------------------------------------------------------------
# Edge cases.
# ---------------------------------------------------------------------------


def test_empty_source():
    assert _check("") == []


def test_whitespace_only_source():
    assert _check("\n\n   \n") == []


def test_comment_only_source():
    assert _check("# just a comment\n") == []


def test_syntax_error_returns_empty():
    assert _check("def f(:\n    pass") == []


def test_syntax_error_unclosed_paren_returns_empty():
    assert _check("x = token == (\n") == []


def test_chained_comparison_not_flagged():
    """`a == token == b` has two operators, so the single-op guard skips it."""
    src = "def f(a, token, b):\n    return a == token == b\n"
    assert _check(src) == []


def test_chained_comparison_all_secrets_not_flagged():
    src = "def f(token, secret, digest):\n    return token == secret == digest\n"
    assert _check(src) == []


def test_secret_vs_secret_attribute_single_diag():
    src = "def f(token, obj):\n    return token == obj.secret\n"
    assert _count(src) == 1


# ---------------------------------------------------------------------------
# Line / column precision.
# ---------------------------------------------------------------------------


def test_line_and_col_module_level():
    diags = _check("token == expected\n")
    assert len(diags) == 1
    assert diags[0].line == 1
    assert diags[0].col == 1


def test_line_and_col_offset_within_statement():
    diags = _check("result = api_key != given\n")
    assert len(diags) == 1
    assert diags[0].line == 1
    assert diags[0].col == 10


def test_line_reported_for_deeper_statement():
    src = "def f(token, e):\n    x = 1\n    return token == e\n"
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].line == 3


def test_col_for_indented_comparison():
    src = "def f(token, e):\n    return token == e\n"
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].col == 12


# ---------------------------------------------------------------------------
# Multiple diagnostics: count and ordering.
# ---------------------------------------------------------------------------


def test_multiple_secrets_each_flagged():
    src = "a = token == x\nb = secret == y\nc = password == z\n"
    diags = _check(src)
    assert len(diags) == 3


def test_multiple_diagnostics_in_source_order():
    src = "a = token == x\nb = secret == y\nc = password == z\n"
    lines = [d.line for d in _check(src)]
    assert lines == sorted(lines)
    assert lines == [1, 2, 3]


def test_mixed_flagged_and_clean_lines():
    src = (
        "import hmac\na = token == x\nb = count == 0\nc = hmac.compare_digest(sig, expected)\nd = signature != given\n"
    )
    diags = _check(src)
    assert [d.line for d in diags] == [2, 5]


# ---------------------------------------------------------------------------
# False-positive class: whole-token matching + innocuous-marker denylist.
# ---------------------------------------------------------------------------

_NON_SECRET_LOOKALIKES = [
    "token_count",
    "token_budget",
    "token_limit",
    "max_tokens",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "n_tokens",
    "num_tokens",
    "tokenize",
    "tokenizer",
    "secretary",
    "api_key_id",
    "webhook_key_id",
    "password_enabled",
    "token_present",
    "secret_present",
    "password_set",
    "password_configured",
    "token_type",
    "credential_type",
]


@pytest.mark.parametrize("name", _NON_SECRET_LOOKALIKES)
def test_allows_non_secret_lookalike_vs_variable(name: str):
    """LLM counters, key-row ids, and feature flags are not secrets even vs a variable."""
    src = f"def f({name}, other):\n    return {name} == other\n"
    assert _check(src) == []


def test_still_flags_password_compound_label():
    """A real secret word as a whole token, vs a runtime value, is still flagged."""
    src = "def f(password_field, submitted):\n    return password_field == submitted\n"
    assert _count(src) == 1


# ---------------------------------------------------------------------------
# Test-path scope: fixture equality assertions are not a timing surface.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("test_path", ["test_auth.py", "svc/tests/test_auth.py", "tests/conftest.py"])
def test_skips_test_paths(test_path: str):
    src = "def f(api_key, fixture_key):\n    return api_key == fixture_key\n"
    assert PreferConstantTimeSecretCompare().check(Path(test_path), src) == []


def test_flags_same_compare_in_production_path():
    """The identical runtime compare in a non-test module is still flagged."""
    src = "def f(api_key, provided):\n    return api_key == provided\n"
    assert len(PreferConstantTimeSecretCompare().check(Path("svc/auth.py"), src)) == 1


# ---------------------------------------------------------------------------
# Adversarial edge-case hunt (2026-07): camelCase, attribute/attribute,
# lambda/f-string operands, innocuous-boundary probing.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["apiKey", "accessToken", "clientSecret", "authToken"])
def test_flags_camelcase_secret_name(name: str):
    """A secret word surfaced only by camelCase splitting is still flagged."""
    src = f"def f({name}, provided):\n    return {name} == provided\n"
    assert _count(src) == 1


def test_flags_attribute_vs_attribute():
    """`self.token == other.token` — both operands secret attrs, one diagnostic."""
    src = "def f(self, other):\n    return self.token == other.token\n"
    assert _count(src) == 1


def test_flags_comparison_inside_lambda():
    src = "g = lambda token, e: token == e\n"
    assert _count(src) == 1


def test_flags_secret_vs_fstring_rhs():
    """An f-string RHS is not a compile-time Constant, so it does not exempt."""
    src = 'def f(token, expected):\n    return token == f"{expected}"\n'
    assert _count(src) == 1


def test_allows_fstring_lhs_not_inspected():
    """A JoinedStr operand is neither Name nor Attribute — out of scope (no fire)."""
    src = 'def f(token, expected):\n    return f"{token}" == expected\n'
    assert _check(src) == []


def test_token_fires_but_token_type_stays_exempt():
    """`token` is a secret; `token_type` (innocuous `type`) is metadata."""
    assert _count("def f(token, o):\n    return token == o\n") == 1
    assert _check("def f(token_type, o):\n    return token_type == o\n") == []


def test_flags_token_tag_tag_absent_from_denylist():
    """`tag` is NOT in the innocuous denylist, so `token_tag` still fires."""
    src = "def f(token_tag, other):\n    return token_tag == other\n"
    assert _count(src) == 1


# --- Genuine defects: xfail(strict=True) ----------------------------------


def test_flags_secret_in_walrus_operand():
    src = "def f(expected):\n    return (secret := load()) == expected\n"
    assert _count(src) == 1


def test_flags_valid_token_credential():
    src = "def f(valid_token, provided):\n    return valid_token == provided\n"
    assert _count(src) == 1


@pytest.mark.xfail(strict=True, reason="Literal-sentinel exemption doesn't follow a Name bound to a str literal one line up — false positive on equivalent code")
def test_allows_secret_vs_name_bound_to_literal():
    src = 'def f(token):\n    expected = "PLACEHOLDER"\n    return token == expected\n'
    assert _check(src) == []
