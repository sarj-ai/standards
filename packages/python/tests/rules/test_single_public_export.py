from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from sarj_python_lint.rules.single_public_export import SinglePublicExport


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic


def _check(source: str, path: str) -> list[Diagnostic]:
    return SinglePublicExport().check(Path(path), source)


def test_junk_drawer_single_class_flagged():
    src = """
class IntegrationProvider: ...
"""
    diags = _check(src, path="enums.py")
    assert len(diags) == 1
    assert "integration_provider.py" in diags[0].message
    assert "junk-drawer" in diags[0].message


def test_junk_drawer_single_function_flagged():
    src = """
def snake_case_text(value: str) -> str: ...
"""
    diags = _check(src, path="utils.py")
    assert len(diags) == 1
    assert "snake_case_text.py" in diags[0].message


def test_informative_stem_not_flagged():
    src = """
class InvalidPaginationCursorError(Exception): ...
"""
    assert _check(src, path="pagination.py") == []


def test_informative_stem_predicate_not_flagged():
    src = """
def is_rate_limit_error(exc: Exception) -> bool: ...
"""
    assert _check(src, path="retry_wrapper.py") == []


def test_junk_drawer_multiple_public_defs_out_of_scope():
    src = """
class A: ...

def gc_once() -> None: ...
"""
    assert _check(src, path="utils.py") == []


def test_junk_drawer_export_already_matches_stem_not_flagged():
    src = """
class Base: ...
"""
    assert _check(src, path="base.py") == []


def test_junk_drawer_private_helpers_and_constants_ignored():
    src = """
THRESHOLD = 300

class Language: ...

def _normalize(x: str) -> str: ...

_CACHE: dict[int, bool] = {}
"""
    diags = _check(src, path="types.py")
    assert len(diags) == 1
    assert "language.py" in diags[0].message


def test_junk_drawer_zero_public_defs_not_flagged():
    src = """
THRESHOLD = 300
_PATTERN = "x"
"""
    assert _check(src, path="constants.py") == []


def test_init_conftest_and_tests_skipped():
    src = """
class OnlyExport: ...
"""
    assert _check(src, path="__init__.py") == []
    assert _check(src, path="conftest.py") == []
    assert _check(src, path="test_things.py") == []
    assert _check(src, path="pkg/tests/utils.py") == []


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("HTTPServer", "http_server"),
        ("JWTHandler", "jwt_handler"),
        ("IVRNavigationTool", "ivr_navigation_tool"),
        ("OAuthService", "oauth_service"),
        ("SalesforceOAuthService", "salesforce_oauth_service"),
        ("MultiprocJanitor", "multiproc_janitor"),
        ("SalesforceTokenResponse", "salesforce_token_response"),
        ("MessagingProviderClient", "messaging_provider_client"),
        ("HTTPServerProbe", "http_server_probe"),
        ("APIKey", "api_key"),
    ],
)
def test_snake_case_acronym_shapes_in_rename_suggestion(name: str, expected: str):
    src = f"""
class {name}: ...
"""
    diags = _check(src, path="base.py")
    assert len(diags) == 1
    assert f"`{expected}.py`" in diags[0].message


def test_oauth_stem_matching_accepted_form_not_flagged():
    src = """
class SalesforceOAuthService: ...
"""
    assert _check(src, path="salesforce_oauth_service.py") == []
