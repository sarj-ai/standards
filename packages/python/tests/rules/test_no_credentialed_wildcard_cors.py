from pathlib import Path
from typing import TYPE_CHECKING

from sarj_python_lint.rules.no_credentialed_wildcard_cors import (
    NoCredentialedWildcardCors,
)


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic


def _check(source: str) -> list[Diagnostic]:
    return NoCredentialedWildcardCors().check(Path("<test>.py"), source)


def test_flags_add_middleware_wildcard_with_credentials():
    src = """
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True)
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ024"


def test_flags_direct_cors_middleware_call():
    src = """
middleware = CORSMiddleware(app, allow_origins=["*"], allow_credentials=True)
"""
    assert len(_check(src)) == 1


def test_flags_attribute_qualified_middleware():
    src = """
app.add_middleware(
    cors.CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
)
"""
    assert len(_check(src)) == 1


def test_flags_multiline_with_other_kwargs():
    src = """
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
"""
    assert len(_check(src)) == 1


def test_flags_wildcard_among_other_origins():
    src = """
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.example.com", "*"],
    allow_credentials=True,
)
"""
    assert len(_check(src)) == 1


def test_flags_conditional_wildcard_fallback():
    """The wildcard-fallback pattern found live in bulbul create_app.py."""
    src = """
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if settings.cors_origins else ["*"],
)
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ024"


def test_flags_conditional_wildcard_in_body_branch():
    src = """
configure_cors(allow_origins=["*"] if debug else settings.cors_origins)
"""
    assert len(_check(src)) == 1


def test_allows_wildcard_without_credentials():
    """Internal/public wildcard CORS without credentials is legitimate."""
    src = """
app.add_middleware(CORSMiddleware, allow_origins=["*"])
"""
    assert _check(src) == []


def test_allows_wildcard_with_credentials_false():
    src = """
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False)
"""
    assert _check(src) == []


def test_allows_explicit_origins_with_credentials():
    src = """
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.example.com"],
    allow_credentials=True,
)
"""
    assert _check(src) == []


def test_allows_credentials_variable_not_literal_true():
    """`allow_credentials=some_var` isn't a literal True — stay conservative."""
    src = """
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=flag)
"""
    assert _check(src) == []


def test_allows_conditional_without_wildcard():
    src = """
app.add_middleware(
    CORSMiddleware,
    allow_origins=prod_origins if is_prod else dev_origins,
)
"""
    assert _check(src) == []


def test_allows_non_cors_call_with_matching_kwargs():
    """Pattern (a) requires CORSMiddleware in the call — arbitrary callees don't trigger."""
    src = """
configure(allow_origins=["*"], allow_credentials=True)
"""
    assert _check(src) == []


def test_handles_syntax_error():
    assert _check("def f(:\n    pass") == []
