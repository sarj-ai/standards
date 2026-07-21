from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from sarj_python_lint.rule_base import is_suppressed
from sarj_python_lint.rules.prefer_struct_over_namedtuple import (
    PreferStructOverNamedtuple,
)


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic


def _check(source: str, path: str = "<t>.py") -> list[Diagnostic]:
    return PreferStructOverNamedtuple().check(Path(path), source)


# --- Metadata ----------------------------------------------------------------


def test_rule_identity():
    rule = PreferStructOverNamedtuple()
    assert rule.code == "SARJ015"
    assert rule.id == "prefer-struct-over-namedtuple"
    assert rule.description


def test_diag_carries_code_and_message():
    diags = _check("from collections import namedtuple\n")
    assert len(diags) == 1
    assert diags[0].code == "SARJ015"
    assert "typing.NamedTuple" in diags[0].message
    assert "pydantic" in diags[0].message


# --- Positive: `from collections import namedtuple` --------------------------


def test_flags_from_collections_import_namedtuple():
    diags = _check("from collections import namedtuple\n")
    assert len(diags) == 1
    assert diags[0].line == 1
    assert diags[0].col == 1


def test_flags_aliased_from_import():
    """`asname` is irrelevant — the original name `namedtuple` is what matters."""
    assert len(_check("from collections import namedtuple as nt\n")) == 1


def test_flags_redundant_self_aliased_from_import():
    assert len(_check("from collections import namedtuple as namedtuple\n")) == 1


def test_flags_parenthesized_from_import():
    assert len(_check("from collections import (namedtuple)\n")) == 1


@pytest.mark.parametrize(
    "src",
    [
        "from collections import namedtuple, defaultdict\n",
        "from collections import defaultdict, namedtuple\n",
        "from collections import OrderedDict, namedtuple, deque\n",
        "from collections import namedtuple, Counter, deque\n",
    ],
)
def test_flags_namedtuple_among_other_collections_imports(src: str):
    assert len(_check(src)) == 1


def test_flags_each_of_multiple_from_imports_on_separate_lines():
    src = "from collections import namedtuple\nfrom collections import namedtuple as nt\n"
    diags = _check(src)
    assert len(diags) == 2
    assert diags[0].line == 1
    assert diags[1].line == 2


# --- Positive: qualified `collections.namedtuple(...)` calls ------------------


def test_flags_qualified_collections_namedtuple_call():
    src = 'import collections\nRow = collections.namedtuple("Row", "id name")\n'
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].line == 2
    assert diags[0].col == 7


def test_flags_qualified_call_without_explicit_import():
    """The call branch keys off the name `collections`, not a tracked import."""
    src = 'Row = collections.namedtuple("Row", ["id", "name"])\n'
    assert len(_check(src)) == 1


@pytest.mark.parametrize("alias", ["c", "col", "_c", "collections_mod", "cx"])
def test_flags_aliased_collections_import_call(alias: str):
    src = f'import collections as {alias}\nRow = {alias}.namedtuple("Row", "id name")\n'
    assert len(_check(src)) == 1


def test_flags_multiple_qualified_calls():
    src = (
        "import collections\n"
        'A = collections.namedtuple("A", ["x"])\n'
        'B = collections.namedtuple("B", ["y"])\n'
        'C = collections.namedtuple("C", ["z"])\n'
    )
    diags = _check(src)
    assert len(diags) == 3
    assert [d.line for d in diags] == [2, 3, 4]


def test_flags_call_inside_function_body():
    src = """
import collections

def make():
    Row = collections.namedtuple("Row", ["x"])
    return Row
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].line == 5


def test_flags_call_inside_class_body():
    src = """
import collections

class Holder:
    Row = collections.namedtuple("Row", ["x"])
"""
    assert len(_check(src)) == 1


def test_flags_call_inside_conditional():
    src = """
import collections

if True:
    Row = collections.namedtuple("Row", ["x"])
"""
    assert len(_check(src)) == 1


def test_flags_call_as_base_class():
    src = """
import collections

class Point(collections.namedtuple("Point", ["x", "y"])):
    pass
"""
    assert len(_check(src)) == 1


def test_flags_nested_call_argument():
    src = 'import collections\nregister(collections.namedtuple("Row", ["x"]))\n'
    assert len(_check(src)) == 1


# --- Positive: import + call together ----------------------------------------


def test_flags_both_import_and_call_sites():
    src = """
from collections import namedtuple
import collections
A = collections.namedtuple("A", ["x"])
"""
    diags = _check(src)
    assert len(diags) == 2
    assert diags[0].line == 2
    assert diags[1].line == 4


def test_functional_call_via_from_import_counts_import_only():
    """A bare-name `namedtuple(...)` call is NOT a second finding; only the import is."""
    src = 'from collections import namedtuple\nPoint = namedtuple("Point", ["x", "y"])\n'
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].line == 1


# --- Negative: typing.NamedTuple is the recommended form ---------------------


def test_allows_typing_namedtuple_class():
    src = """
from typing import NamedTuple
class Point(NamedTuple):
    x: float
    y: float
"""
    assert _check(src) == []


def test_allows_typing_namedtuple_import_alone():
    assert _check("from typing import NamedTuple\n") == []


def test_allows_qualified_typing_namedtuple_class():
    src = """
import typing
class Point(typing.NamedTuple):
    x: float
"""
    assert _check(src) == []


def test_allows_typing_namedtuple_functional_call():
    src = 'from typing import NamedTuple\nPoint = NamedTuple("Point", [("x", int)])\n'
    assert _check(src) == []


# --- Negative: other collections members -------------------------------------


@pytest.mark.parametrize(
    "src",
    [
        "from collections import defaultdict\n",
        "from collections import defaultdict, Counter\n",
        "from collections import OrderedDict, deque, ChainMap\n",
        "from collections.abc import Mapping, Sequence\n",
        "from collections.abc import Callable\n",
    ],
)
def test_allows_non_namedtuple_collections_imports(src: str):
    assert _check(src) == []


def test_allows_collections_abc_namedtuple_lookalike():
    """A submodule import (`collections.abc`) is not `module == 'collections'`."""
    src = "from collections.abc import Sequence\nimport collections\n"
    assert _check(src) == []


# --- Negative / false-positive guards ----------------------------------------


def test_allows_bare_namedtuple_call_without_import():
    """A bare `namedtuple(...)` Name-call is not attributed to collections here."""
    src = 'Point = namedtuple("Point", ["x", "y"])\n'
    assert _check(src) == []


def test_allows_unrelated_attribute_namedtuple_call():
    assert _check("result = obj.namedtuple()\n") == []


def test_allows_nested_attribute_namedtuple_call():
    """`foo.collections.namedtuple(...)` — func.value is an Attribute, not a Name."""
    src = 'Row = foo.collections.namedtuple("Row", ["x"])\n'
    assert _check(src) == []


def test_allows_unrelated_module_namedtuple_call():
    src = 'import mymod\nRow = mymod.namedtuple("Row", ["x"])\n'
    assert _check(src) == []


def test_allows_collections_namedtuple_attribute_without_call():
    """Only *calls* are flagged; a bare reference to the attribute is not."""
    src = "import collections\nfactory = collections.namedtuple\n"
    assert _check(src) == []


def test_allows_variable_named_namedtuple():
    src = "namedtuple = 5\nx = namedtuple + 1\n"
    assert _check(src) == []


def test_allows_annotation_named_namedtuple():
    src = "namedtuple: int = 0\n"
    assert _check(src) == []


def test_allows_string_annotation_mentioning_namedtuple():
    src = 'def f() -> "collections.namedtuple": ...\n'
    assert _check(src) == []


def test_allows_import_collections_without_use():
    assert _check("import collections\n") == []


def test_allows_collections_import_with_unrelated_name_call():
    src = "import collections\nx.namedtuple()\n"
    assert _check(src) == []


def test_allows_docstring_mentioning_namedtuple():
    src = '"""Use collections.namedtuple sparingly."""\n'
    assert _check(src) == []


# --- Edge cases: empty / malformed input -------------------------------------


@pytest.mark.parametrize("src", ["", "\n", "   \n\t\n", "# just a comment\n"])
def test_empty_or_trivial_source_is_clean(src: str):
    assert _check(src) == []


@pytest.mark.parametrize(
    "src",
    [
        "def broken(:\n",
        "from collections import namedtuple\nRow = collections.namedtuple(\n",
        "class :\n    pass\n",
        "x = = 5\n",
    ],
)
def test_syntax_error_returns_empty_without_crashing(src: str):
    assert _check(src) == []


# --- Line / column precision on multiple diagnostics -------------------------


def test_line_and_col_of_two_distinct_findings():
    src = "from collections import namedtuple\nimport collections as c\nR = c.namedtuple('R', ['a'])\n"
    diags = _check(src)
    assert len(diags) == 2
    assert (diags[0].line, diags[0].col) == (1, 1)
    assert (diags[1].line, diags[1].col) == (3, 5)


def test_finding_order_follows_ast_walk_not_source_position():
    """`ast.walk` is breadth-first: import findings (direct Module children) precede
    call findings (nested in Assign), so output is not strictly source-sorted."""
    src = (
        "import collections\n"
        'A = collections.namedtuple("A", ["x"])\n'
        "from collections import namedtuple\n"
        'B = collections.namedtuple("B", ["y"])\n'
    )
    diags = _check(src)
    assert sorted(d.line for d in diags) == [2, 3, 4]
    assert [d.line for d in diags] == [3, 2, 4]


# --- Suppression is a CLI-layer concern, not applied by check() --------------


def test_check_does_not_apply_sarj_noqa():
    """The rule reports regardless of `# sarj-noqa`; suppression happens upstream."""
    src = "from collections import namedtuple  # sarj-noqa: SARJ015 — legacy\n"
    assert len(_check(src)) == 1


def test_is_suppressed_recognizes_code_on_reported_line():
    src = "from collections import namedtuple  # sarj-noqa: SARJ015 — legacy\n"
    diags = _check(src)
    assert len(diags) == 1
    assert is_suppressed(src.splitlines(), diags[0].line, diags[0].code)


def test_is_suppressed_false_for_unrelated_code():
    src = "from collections import namedtuple  # sarj-noqa: SARJ001 — other\n"
    diags = _check(src)
    assert not is_suppressed(src.splitlines(), diags[0].line, diags[0].code)


# --- Regression pins for static-name-matching limitations --------------------


def test_shadowed_collections_name_still_fires():
    """Accepted limitation: name-based matching fires even on a rebound `collections`."""
    src = 'collections = object()\nRow = collections.namedtuple("Row", ["x"])\n'
    assert len(_check(src)) == 1
