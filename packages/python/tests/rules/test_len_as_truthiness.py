from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from sarj_python_lint.rules.len_as_truthiness import LenAsTruthiness


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic


def _check(source: str) -> list[Diagnostic]:
    return LenAsTruthiness().check(Path("<t>.py"), source)


# --------------------------------------------------------------------------- #
# Positive: the six zero-boundary truthiness forms                             #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("expr", "suggestion"),
    [
        ("len(x) == 0", "not x"),
        ("len(x) < 1", "not x"),
        ("len(x) <= 0", "not x"),
        ("len(x) != 0", "x"),
        ("len(x) > 0", "x"),
        ("len(x) >= 1", "x"),
    ],
)
def test_flags_each_zero_boundary_form(expr: str, suggestion: str):
    diags = _check(f"if {expr}:\n    a()\n")
    assert len(diags) == 1
    assert diags[0].code == "SARJ027"
    assert f"`{suggestion}`" in diags[0].message


# --------------------------------------------------------------------------- #
# Negative: exact-count / other-boundary size checks must NOT fire             #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "expr",
    [
        "len(x) == 1",
        "len(x) >= 2",
        "len(x) > 1",
        "len(x) < 2",
        "len(x) == 3",
        "len(x) != 1",
        "len(x) <= 1",
        "len(x) < 0",
        "len(x) > 2",
        "len(x) == 2",
        "len(x) >= 0",
    ],
)
def test_does_not_flag_non_truthiness_count_checks(expr: str):
    assert _check(f"if {expr}:\n    a()\n") == []


# --------------------------------------------------------------------------- #
# Positive: the argument to len can be any expression                          #
# --------------------------------------------------------------------------- #


def test_flags_len_on_attribute_argument():
    assert len(_check("if len(obj.items) == 0:\n    a()\n")) == 1


def test_flags_len_on_subscript_argument():
    assert len(_check("if len(rows[0]) > 0:\n    a()\n")) == 1


def test_flags_len_on_call_argument():
    assert len(_check("if len(fetch()) != 0:\n    a()\n")) == 1


def test_flags_len_in_boolean_context_expression():
    assert len(_check("ok = len(items) > 0 and ready\n")) == 1


def test_flags_len_in_assert_and_return():
    src = """
def f(x):
    assert len(x) != 0
    return len(x) == 0
"""
    assert len(_check(src)) == 2


# --------------------------------------------------------------------------- #
# Negative: not literally `len(<one expr>)`                                    #
# --------------------------------------------------------------------------- #


def test_does_not_flag_non_len_call():
    assert _check("if count(x) == 0:\n    a()\n") == []


def test_does_not_flag_len_via_attribute():
    assert _check("if obj.len(x) == 0:\n    a()\n") == []


def test_does_not_flag_len_with_no_args():
    assert _check("if len() == 0:\n    a()\n") == []


def test_does_not_flag_len_with_two_args():
    assert _check("if len(a, b) == 0:\n    a()\n") == []


def test_does_not_flag_len_with_star_arg():
    assert _check("if len(*args) == 0:\n    a()\n") == []


def test_does_not_flag_len_with_keyword_arg():
    assert _check("if len(obj=x) == 0:\n    a()\n") == []


# --------------------------------------------------------------------------- #
# Negative: wrong right-hand side                                             #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("rhs", ["2", "10", "-1", "0.0", "n", "len(y)", "'0'"])
def test_does_not_flag_non_zero_one_rhs(rhs: str):
    assert _check(f"if len(x) == {rhs}:\n    a()\n") == []


@pytest.mark.parametrize("rhs", ["True", "False"])
def test_does_not_flag_bool_rhs(rhs: str):
    assert _check(f"if len(x) == {rhs}:\n    a()\n") == []


# --------------------------------------------------------------------------- #
# Negative: chained comparisons and empty-literal checks                       #
# --------------------------------------------------------------------------- #


def test_does_not_flag_chained_comparison():
    assert _check("if 0 < len(x) < 5:\n    a()\n") == []


def test_does_not_flag_double_ended_chain():
    assert _check("if 0 <= len(x) <= 0:\n    a()\n") == []


def test_does_not_flag_empty_list_literal_check():
    assert _check("if x == []:\n    a()\n") == []


def test_does_not_flag_empty_dict_literal_check():
    assert _check("if x == {}:\n    a()\n") == []


def test_does_not_flag_yoda_form():
    # Yoda `0 == len(x)` is intentionally out of scope (LHS is not the len call).
    assert _check("if 0 == len(x):\n    a()\n") == []


# --------------------------------------------------------------------------- #
# Line / column precision + ordering                                           #
# --------------------------------------------------------------------------- #


def test_line_and_col_at_module_level():
    diags = _check("if len(x) == 0:\n    a()\n")
    assert len(diags) == 1
    assert diags[0].line == 1
    assert diags[0].col == 4


def test_line_and_col_when_nested():
    src = """
class C:
    def f(self, x):
        if len(x) > 0:
            a()
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].line == 4
    assert diags[0].col == 12


def test_multiple_findings_sorted_by_line_then_col():
    src = """
def f(x, y):
    a = len(x) == 0 or len(y) != 0
    b = len(x) > 0
"""
    diags = _check(src)
    assert len(diags) == 3
    assert [(d.line, d.col) for d in diags] == sorted((d.line, d.col) for d in diags)


# --------------------------------------------------------------------------- #
# Diagnostic metadata                                                          #
# --------------------------------------------------------------------------- #


def test_diagnostic_carries_path_and_code():
    diags = LenAsTruthiness().check(Path("svc/thing.py"), "if len(x) == 0:\n    a()\n")
    assert len(diags) == 1
    assert diags[0].path == Path("svc/thing.py")
    assert diags[0].code == "SARJ027"


# --------------------------------------------------------------------------- #
# Edge cases: empty / whitespace / syntax error                               #
# --------------------------------------------------------------------------- #


def test_empty_source_returns_empty():
    assert _check("") == []


def test_whitespace_only_source_returns_empty():
    assert _check("\n   \n\t\n") == []


def test_syntax_error_returns_empty():
    assert _check("def broken(:\n") == []


def test_syntax_error_amid_valid_compare_returns_empty():
    src = """
def f(x):
    if len(x) == 0:
        a(
"""
    assert _check(src) == []
