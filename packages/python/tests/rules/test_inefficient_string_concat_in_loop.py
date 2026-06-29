from pathlib import Path
from typing import TYPE_CHECKING

from sarj_python_lint.rules.inefficient_string_concat_in_loop import (
    InefficientStringConcatInLoop,
)


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic


def _check(source: str) -> list[Diagnostic]:
    return InefficientStringConcatInLoop().check(Path("<t>.py"), source)


def test_flags_string_concat_in_for():
    src = """
def f(items):
    s = ""
    for x in items:
        s += "prefix " + str(x)
"""
    assert len(_check(src)) == 1


def test_flags_fstring_concat_in_while():
    src = """
def f(n):
    s = ""
    i = 0
    while i < n:
        s += f"row {i}"
        i += 1
"""
    assert len(_check(src)) == 1


def test_allows_integer_accumulator():
    src = """
def f(items):
    total = 0
    for x in items:
        total += x
"""
    assert _check(src) == []


def test_allows_list_append():
    src = """
def f(items):
    parts = []
    for x in items:
        parts.append(str(x))
    return "".join(parts)
"""
    assert _check(src) == []


def test_nested_loops_report_each_concat_once():
    """A concat in nested loops is reported once, not once per ancestor loop."""
    src = """
def f(rows):
    s = ""
    for row in rows:
        for cell in row:
            s += str(cell)
    return s
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ002"
