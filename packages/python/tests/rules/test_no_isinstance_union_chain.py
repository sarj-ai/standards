from pathlib import Path
from typing import TYPE_CHECKING

from sarj_python_lint.rules.no_isinstance_union_chain import NoIsinstanceUnionChain


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic


def _check(source: str) -> list[Diagnostic]:
    return NoIsinstanceUnionChain().check(Path("<t>.py"), source)


def test_flags_two_branch_chain_over_local_classes():
    src = """
def handle(subject):
    if isinstance(subject, ApiKeySubject):
        a()
    elif isinstance(subject, JwtSubject):
        b()
"""
    diags = _check(src)
    assert len(diags) == 1
    assert "2 types" in diags[0].message


def test_flags_three_branch_chain_with_else():
    src = """
def handle(node):
    if isinstance(node, DraftScenario):
        a()
    elif isinstance(node, PublishedScenario):
        b()
    elif isinstance(node, ArchivedScenario):
        c()
    else:
        d()
"""
    diags = _check(src)
    assert len(diags) == 1
    assert "3 types" in diags[0].message


def test_flags_chain_with_dotted_class_refs():
    src = """
def handle(evt):
    if isinstance(evt, events.Created):
        a()
    elif isinstance(evt, events.Deleted):
        b()
"""
    assert len(_check(src)) == 1


def test_allows_single_isinstance_guard():
    src = """
def handle(x):
    if isinstance(x, CustomScenario):
        a()
"""
    assert _check(src) == []


def test_allows_tuple_membership_check():
    src = """
def handle(x):
    if isinstance(x, (ApiKeySubject, JwtSubject)):
        a()
    else:
        b()
"""
    assert _check(src) == []


def test_allows_chain_touching_builtin_dict():
    src = """
def handle(x):
    if isinstance(x, ScenarioMapping):
        a()
    elif isinstance(x, dict):
        b()
"""
    assert _check(src) == []


def test_allows_chain_touching_str():
    src = """
def handle(x):
    if isinstance(x, FlushSentinel):
        a()
    elif isinstance(x, str):
        b()
"""
    assert _check(src) == []


def test_allows_chain_touching_unset_sentinel():
    src = """
def handle(x):
    if isinstance(x, RealValue):
        a()
    elif isinstance(x, Unset):
        b()
"""
    assert _check(src) == []


def test_allows_exception_dispatch():
    src = """
def handle(err):
    if isinstance(err, ValueError):
        a()
    elif isinstance(err, BaseException):
        b()
"""
    assert _check(src) == []


def test_allows_mixed_isinstance_and_hasattr_guard():
    src = """
def handle(first_mapping):
    if hasattr(first_mapping, "scenario_id"):
        a()
    elif isinstance(first_mapping, dict):
        b()
"""
    assert _check(src) == []


def test_allows_chain_on_different_targets():
    src = """
def handle(x, y):
    if isinstance(x, Foo):
        a()
    elif isinstance(y, Bar):
        b()
"""
    assert _check(src) == []


def test_allows_isinstance_combined_with_boolean():
    src = """
def handle(x):
    if isinstance(x, Foo) and x.ready:
        a()
    elif isinstance(x, Bar):
        b()
"""
    assert _check(src) == []


def test_allows_already_using_match():
    src = """
from typing import assert_never

def handle(subject):
    match subject:
        case ApiKeySubject():
            a()
        case JwtSubject():
            b()
        case _:
            assert_never(subject)
"""
    assert _check(src) == []


def test_syntax_error_returns_empty():
    assert _check("def broken(:\n") == []
