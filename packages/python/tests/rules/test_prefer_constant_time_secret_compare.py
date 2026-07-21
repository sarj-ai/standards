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


def test_flags_secret_vs_nonempty_string_literal():
    """A non-empty string literal is a real value, so the compare is flagged."""
    src = 'def f(token):\n    return token == "expected-value"\n'
    assert _count(src) == 1


def test_flags_comparison_inside_comprehension():
    src = "def f(items, token):\n    return [x for x in items if token == x]\n"
    assert _count(src) == 1


def test_flags_comparison_under_not():
    src = "def f(token, expected):\n    return not (token == expected)\n"
    assert _count(src) == 1


def test_flags_secret_name_as_substring():
    """The pattern matches anywhere in the identifier, not just whole words."""
    src = "def f(subtoken, other):\n    return subtoken == other\n"
    assert _count(src) == 1


@pytest.mark.parametrize(
    "identifier",
    ["mytokenvalue", "user_password_check", "the_signature_bytes", "x_hmac_y"],
)
def test_flags_embedded_secret_substrings(identifier: str):
    src = f"def f({identifier}, other):\n    return {identifier} == other\n"
    assert _count(src) == 1


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
# False-positive awareness: broad substring matching is intentional.
# ---------------------------------------------------------------------------


def test_broad_regex_flags_token_count_vs_variable():
    """Documented behavior: the substring match flags `token_count == other`.

    The exemption only fires for numeric/None/empty-string literals, so a
    count-like name compared to another *variable* is still reported.
    """
    src = "def f(token_count, other_count):\n    return token_count == other_count\n"
    assert _count(src) == 1


def test_broad_regex_flags_password_field_label():
    src = 'def f(password_field_label):\n    return password_field_label == "Password"\n'
    assert _count(src) == 1
