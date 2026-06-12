from pathlib import Path

from sarj_python_lint.rules.prefer_constant_time_secret_compare import (
    PreferConstantTimeSecretCompare,
)


def _check(source: str) -> list:
    return PreferConstantTimeSecretCompare().check(Path("<test>.py"), source)


def test_flags_token_eq():
    src = """
def f(token, expected):
    if token == expected:
        return True
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ010"


def test_flags_signature_neq_hmac():
    src = """
def f(sig, computed_hmac):
    if sig != computed_hmac:
        return False
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ010"


def test_flags_attribute_password_hash():
    src = """
def f(user, provided):
    return user.password_hash == provided
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ010"


def test_allows_token_is_none():
    src = """
def f(token):
    if token is None:
        return True
"""
    assert _check(src) == []


def test_allows_count_eq_zero():
    src = """
def f(count):
    if count == 0:
        return True
"""
    assert _check(src) == []


def test_allows_non_secret_name():
    src = """
def f(name):
    if name == "admin":
        return True
"""
    assert _check(src) == []


def test_allows_compare_digest():
    src = """
import hmac

def f(token, expected):
    return hmac.compare_digest(token, expected)
"""
    assert _check(src) == []


def test_allows_token_none_eq():
    """`token == None` is a presence check, not a secret comparison."""
    src = """
def f(token):
    if token == None:
        return True
"""
    assert _check(src) == []


def test_allows_secret_eq_empty_string():
    """`secret == ""` is a length/presence check."""
    src = """
def f(secret):
    if secret == "":
        return True
"""
    assert _check(src) == []


def test_one_diagnostic_per_compare():
    src = """
def f(api_key, expected):
    a = api_key == expected
    return a
"""
    assert len(_check(src)) == 1


def test_handles_syntax_error():
    assert _check("def f(:\n    pass") == []
