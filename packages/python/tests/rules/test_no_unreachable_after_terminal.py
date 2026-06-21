from pathlib import Path

from sarj_python_lint.rules.no_unreachable_after_terminal import (
    NoUnreachableAfterTerminal,
)


def _check(source: str) -> list:
    return NoUnreachableAfterTerminal().check(Path("<test>.py"), source)


def test_flags_statement_after_return():
    src = """
def f():
    return 1
    print("dead")
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ010"


def test_flags_statement_after_raise():
    src = """
def f():
    raise ValueError("boom")
    cleanup()
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ010"


def test_flags_statement_after_break():
    src = """
def f(items):
    for x in items:
        break
        process(x)
"""
    assert len(_check(src)) == 1


def test_flags_statement_after_continue():
    src = """
def f(items):
    for x in items:
        continue
        process(x)
"""
    assert len(_check(src)) == 1


def test_allows_terminal_as_last_statement():
    src = """
def f(x):
    if x:
        return 1
    return 2
"""
    assert _check(src) == []


def test_allows_return_in_one_branch_of_if():
    src = """
def f(x):
    if x:
        return 1
    do_more()
    return 2
"""
    assert _check(src) == []


def test_one_diagnostic_per_list_first_unreachable():
    src = """
def f():
    return 1
    a = 2
    b = 3
"""
    diags = _check(src)
    assert len(diags) == 1


def test_handles_syntax_error():
    assert _check("def f(:\n    pass") == []
