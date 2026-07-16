from pathlib import Path
from typing import TYPE_CHECKING

from sarj_python_lint.rules.no_disabled_tls_verify import NoDisabledTlsVerify


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic


def _check(source: str) -> list[Diagnostic]:
    return NoDisabledTlsVerify().check(Path("<test>.py"), source)


def test_flags_httpx_client_verify_false():
    src = """
import httpx

client = httpx.Client(verify=False)
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ022"


def test_flags_httpx_async_client_verify_false():
    src = """
client = httpx.AsyncClient(base_url=url, verify=False)
"""
    assert len(_check(src)) == 1


def test_flags_httpx_one_shot_get():
    src = """
resp = httpx.get("https://gw.example.com", verify=False)
"""
    assert len(_check(src)) == 1


def test_flags_httpx_stream():
    src = """
with httpx.stream("GET", url, verify=False) as r:
    pass
"""
    assert len(_check(src)) == 1


def test_flags_requests_post():
    src = """
resp = requests.post(url, json=payload, verify=False)
"""
    assert len(_check(src)) == 1


def test_flags_inline_requests_session_chain():
    src = """
resp = requests.Session().get(url, verify=False)
"""
    assert len(_check(src)) == 1


def test_flags_multiline_call():
    src = """
client = httpx.Client(
    base_url="https://api.example.com",
    verify=False,
    headers=headers,
)
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].line == 4


def test_allows_verify_true():
    src = """
client = httpx.Client(verify=True)
"""
    assert _check(src) == []


def test_allows_verify_variable():
    """`verify=some_var` may be a context/bundle path — not resolvable, not flagged."""
    src = """
client = httpx.Client(verify=tls_context)
"""
    assert _check(src) == []


def test_allows_custom_wrapper_kwarg():
    """Custom-wrapper kwargs like `ssl_verify` are documented out of scope."""
    src = """
client = OurHttpClient(ssl_verify=False)
"""
    assert _check(src) == []


def test_allows_verify_false_on_unresolvable_callee():
    """`foo.get(...)` doesn't resolve to httpx/requests — not flagged."""
    src = """
resp = foo.get(url, verify=False)
"""
    assert _check(src) == []


def test_allows_httpx_call_without_verify():
    src = """
resp = httpx.get(url, timeout=5)
"""
    assert _check(src) == []


def test_handles_syntax_error():
    assert _check("def f(:\n    pass") == []
