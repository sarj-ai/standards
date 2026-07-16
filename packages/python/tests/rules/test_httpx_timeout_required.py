from pathlib import Path
from typing import TYPE_CHECKING

from sarj_python_lint.rules.httpx_timeout_required import HttpxTimeoutRequired


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic


def _check(source: str) -> list[Diagnostic]:
    return HttpxTimeoutRequired().check(Path("<test>.py"), source)


def test_flags_client_without_timeout():
    src = """
client = httpx.Client()
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ023"


def test_flags_async_client_with_other_kwargs():
    src = """
client = httpx.AsyncClient(base_url=url, headers=headers)
"""
    assert len(_check(src)) == 1


def test_flags_one_shot_get():
    src = """
resp = httpx.get("https://api.example.com")
"""
    assert len(_check(src)) == 1


def test_flags_one_shot_request():
    src = """
resp = httpx.request("DELETE", url)
"""
    assert len(_check(src)) == 1


def test_flags_multiline_call_without_timeout():
    src = """
client = httpx.AsyncClient(
    base_url="https://api.example.com",
    headers=headers,
)
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].line == 2


def test_allows_timeout_present():
    src = """
client = httpx.Client(timeout=10)
"""
    assert _check(src) == []


def test_allows_timeout_none_explicit_policy():
    """`timeout=None` is an explicit never-time-out policy — accepted."""
    src = """
client = httpx.Client(timeout=None)
"""
    assert _check(src) == []


def test_allows_timeout_present_multiline():
    src = """
client = httpx.AsyncClient(
    base_url="https://api.example.com",
    timeout=httpx.Timeout(30.0, connect=5.0),
)
"""
    assert _check(src) == []


def test_allows_kwargs_spread():
    """A `**spread` might carry timeout — stay conservative."""
    src = """
client = httpx.Client(**client_kwargs)
"""
    assert _check(src) == []


def test_allows_requests_calls():
    """requests is Ruff S113's territory — this rule is httpx-only."""
    src = """
resp = requests.get(url)
"""
    assert _check(src) == []


def test_allows_non_httpx_client():
    src = """
client = storage.Client()
"""
    assert _check(src) == []


def test_handles_syntax_error():
    assert _check("def f(:\n    pass") == []
