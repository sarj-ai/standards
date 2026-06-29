from pathlib import Path

from sarj_python_lint.rules.prefer_struct_over_namedtuple import (
    PreferStructOverNamedtuple,
)


def _check(source: str) -> list:
    return PreferStructOverNamedtuple().check(Path("<t>.py"), source)


def test_flags_from_collections_import_namedtuple():
    src = "from collections import namedtuple\n"
    diags = _check(src)
    assert len(diags) == 1
    assert "typing.NamedTuple" in diags[0].message


def test_flags_qualified_collections_namedtuple_call():
    src = """
import collections
Row = collections.namedtuple("Row", "id name")
"""
    assert len(_check(src)) == 1


def test_flags_both_import_and_call_sites():
    src = """
from collections import namedtuple
import collections
A = collections.namedtuple("A", ["x"])
"""
    assert len(_check(src)) == 2


def test_flags_aliased_collections_import():
    src = """
import collections as c
Row = c.namedtuple("Row", "id name")
"""
    assert len(_check(src)) == 1


def test_allows_typing_namedtuple():
    src = """
from typing import NamedTuple
class Point(NamedTuple):
    x: float
    y: float
"""
    assert _check(src) == []


def test_allows_unrelated_namedtuple_attr():
    src = "result = obj.namedtuple()\n"
    assert _check(src) == []


def test_allows_other_collections_imports():
    src = "from collections import defaultdict, Counter\n"
    assert _check(src) == []
