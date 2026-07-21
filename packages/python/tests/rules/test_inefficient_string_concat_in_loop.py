from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from sarj_python_lint.rules.inefficient_string_concat_in_loop import (
    InefficientStringConcatInLoop,
)


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic


def _check(source: str, path: str = "<t>.py") -> list[Diagnostic]:
    return InefficientStringConcatInLoop().check(Path(path), source)


def _count(source: str) -> int:
    return len(_check(source))


# --------------------------------------------------------------------------- #
# Positive — `s += <string-ish>` inside a loop fires exactly once.            #
# --------------------------------------------------------------------------- #


_STRINGISH_RHS = [
    pytest.param('"literal"', id="rhs-str-constant"),
    pytest.param('f"row {x}"', id="rhs-fstring"),
    pytest.param("str(x)", id="rhs-str-call"),
    pytest.param("repr(x)", id="rhs-repr-call"),
    pytest.param("format(x)", id="rhs-format-builtin"),
    pytest.param('"{}".format(x)', id="rhs-format-method"),
    pytest.param('dt.strftime("%Y")', id="rhs-strftime-method"),
    pytest.param('",".join(bits)', id="rhs-join-method"),
    pytest.param('"prefix " + str(x)', id="rhs-binop-const-left"),
    pytest.param('str(x) + " suffix"', id="rhs-binop-const-right"),
    pytest.param('"a" + "b" + str(x)', id="rhs-binop-nested"),
    pytest.param('prefix + "x"', id="rhs-binop-name-plus-const"),
]


@pytest.mark.parametrize("rhs", _STRINGISH_RHS)
def test_flags_stringish_rhs_in_for(rhs: str):
    src = f"""
def f(items, dt, bits, prefix):
    s = ""
    for x in items:
        s += {rhs}
"""
    assert _count(src) == 1


@pytest.mark.parametrize("rhs", _STRINGISH_RHS)
def test_flags_stringish_rhs_in_while(rhs: str):
    src = f"""
def f(items, dt, bits, prefix):
    s = ""
    x = 0
    while x < 10:
        s += {rhs}
        x += 1
"""
    assert _count(src) == 1


_TARGETS = [
    pytest.param("s", id="target-name"),
    pytest.param("self.buf", id="target-attribute"),
    pytest.param('acc["k"]', id="target-subscript"),
    pytest.param("obj.rows[i]", id="target-attr-subscript"),
]


@pytest.mark.parametrize("target", _TARGETS)
def test_flags_regardless_of_target_shape(target: str):
    src = f"""
def f(self, items, acc, obj, i):
    for x in items:
        {target} += str(x)
"""
    assert _count(src) == 1


def test_flags_for_over_comprehension_iterable():
    src = """
def f(items):
    s = ""
    for x in [i for i in items]:
        s += str(x)
    return s
"""
    assert _count(src) == 1


def test_flags_concat_in_for_else_clause():
    """The `else` block is visited at loop depth, so a concat there fires.

    Documents current behaviour; the else runs once, so this is arguably a
    borderline false positive worth revisiting if the rule tightens.
    """
    src = """
def f(items):
    s = ""
    for x in items:
        pass
    else:
        s += "done"
"""
    assert _count(src) == 1


def test_flags_concat_after_walrus_condition():
    src = """
def f(it):
    s = ""
    while (n := next(it, None)) is not None:
        s += str(n)
    return s
"""
    assert _count(src) == 1


# --------------------------------------------------------------------------- #
# Nesting — each concat is flagged once, never once per ancestor loop.        #
# --------------------------------------------------------------------------- #


def test_nested_for_for_reports_once():
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


def test_nested_while_for_reports_once():
    src = """
def f(rows, n):
    s = ""
    while n > 0:
        for cell in rows:
            s += str(cell)
        n -= 1
"""
    assert _count(src) == 1


def test_deeply_nested_three_levels_reports_once():
    src = """
def f(a):
    s = ""
    for i in a:
        for j in a:
            for k in a:
                s += str(k)
    return s
"""
    assert _count(src) == 1


def test_two_sibling_loops_report_two_diagnostics():
    src = """
def f(a, b):
    s = ""
    for x in a:
        s += str(x)
    for y in b:
        s += repr(y)
    return s
"""
    assert _count(src) == 2


def test_multiple_concats_in_one_loop_flag_each():
    src = """
def f(items):
    s = ""
    t = ""
    for x in items:
        s += str(x)
        t += repr(x)
    return s, t
"""
    assert _count(src) == 2


# --------------------------------------------------------------------------- #
# Diagnostic content — line, col (1-based), code, message.                    #
# --------------------------------------------------------------------------- #


def test_reports_line_and_one_based_column():
    src = 'def f(it):\n    s = ""\n    for x in it:\n        s += str(x)\n'
    (diag,) = _check(src)
    assert (diag.line, diag.col) == (4, 9)
    assert diag.code == "SARJ002"
    assert "O(n" in diag.message


def test_reports_distinct_positions_in_source_order():
    src = 'def f(a, b):\n    s = ""\n    for x in a:\n        s += str(x)\n    for y in b:\n        s += repr(y)\n'
    positions = [(d.line, d.col) for d in _check(src)]
    assert positions == [(4, 9), (6, 9)]


# --------------------------------------------------------------------------- #
# Negative / exempt — the correct patterns and out-of-scope shapes.           #
# --------------------------------------------------------------------------- #


def test_allows_concat_outside_any_loop():
    src = """
def f(a, b):
    s = ""
    s += str(a)
    s += str(b)
    return s
"""
    assert _check(src) == []


def test_allows_module_level_concat():
    assert _check('s = "a"\ns += "b"\n') == []


def test_allows_list_append_in_loop():
    src = """
def f(items):
    parts = []
    for x in items:
        parts.append(str(x))
    return "".join(parts)
"""
    assert _check(src) == []


def test_allows_set_add_in_loop():
    src = """
def f(items):
    seen = set()
    for x in items:
        seen.add(str(x))
    return seen
"""
    assert _check(src) == []


_NON_STRING_AUGASSIGN = [
    pytest.param("total += 1", id="int-literal"),
    pytest.param("total += x", id="name-rhs"),
    pytest.param("total += len(x)", id="len-call-rhs"),
    pytest.param("total += x * 2", id="binop-mult-rhs"),
    pytest.param("acc += [x]", id="list-literal-rhs"),
    pytest.param('buf += b"x"', id="bytes-literal-rhs"),
    pytest.param("acc += (x,)", id="tuple-rhs"),
    pytest.param("total += 1.5", id="float-literal"),
]


@pytest.mark.parametrize("stmt", _NON_STRING_AUGASSIGN)
def test_allows_non_string_augassign_in_loop(stmt: str):
    src = f"""
def f(items):
    total = 0
    acc = []
    buf = b""
    for x in items:
        {stmt}
    return total
"""
    assert _check(src) == []


def test_allows_string_repeat_augassign():
    """`s *= 2` is Mult, not Add — not the concat antipattern."""
    src = """
def f(items):
    s = "-"
    for _ in items:
        s *= 2
    return s
"""
    assert _check(src) == []


def test_allows_fresh_binop_assignment_each_iteration():
    """A plain (non-augmented) assignment to a fresh local is not accumulation."""
    src = """
def f(items):
    for x in items:
        line = "row " + str(x)
        emit(line)
"""
    assert _check(src) == []


def test_allows_string_augassign_from_name_only():
    """RHS is a bare Name — the conservative heuristic does not assume it is a str."""
    src = """
def f(items, chunk):
    s = ""
    for x in items:
        s += chunk
    return s
"""
    assert _check(src) == []


# --------------------------------------------------------------------------- #
# Edge — parse failures, empty input, comments-only.                          #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "source",
    [
        pytest.param("", id="empty"),
        pytest.param("   \n\t\n", id="whitespace-only"),
        pytest.param("# just a comment\n", id="comment-only"),
        pytest.param("def f(:\n    pass\n", id="syntax-error-signature"),
        pytest.param("for x in items\n    s += str(x)\n", id="syntax-error-missing-colon"),
        pytest.param("s += (\n", id="syntax-error-unclosed"),
    ],
)
def test_non_parseable_or_trivial_sources_yield_no_diagnostics(source: str):
    assert _check(source) == []


# --------------------------------------------------------------------------- #
# False-positive guards — accumulators that only look adjacent to strings.    #
# --------------------------------------------------------------------------- #


def test_numeric_accumulation_alongside_string_append_is_clean():
    src = """
def f(items):
    total = 0
    parts = []
    for x in items:
        total += len(x)
        parts.append(str(x))
    return total, "".join(parts)
"""
    assert _check(src) == []


def test_list_building_with_plus_equals_list_is_clean():
    src = """
def f(chunks):
    out = []
    for c in chunks:
        out += list(c)
    return out
"""
    assert _check(src) == []


def test_bytes_accumulation_is_clean():
    src = """
def f(frames):
    buf = b""
    for frame in frames:
        buf += frame.data
    return buf
"""
    assert _check(src) == []


# --------------------------------------------------------------------------- #
# Known gaps / suspected bugs — documented via xfail so the suite stays green #
# while surfacing behaviour that likely warrants a rule fix.                  #
# --------------------------------------------------------------------------- #


@pytest.mark.xfail(
    reason="async for is not treated as a loop; same O(n^2) concat goes undetected",
    strict=False,
)
def test_flags_string_concat_in_async_for():
    src = """
async def f(stream):
    s = ""
    async for chunk in stream:
        s += str(chunk)
    return s
"""
    assert _count(src) == 1


@pytest.mark.xfail(
    reason="`s = s + x` (plain assign) is the same antipattern but only `+=` is handled",
    strict=False,
)
def test_flags_plain_reassignment_concat_in_loop():
    src = """
def f(items):
    s = ""
    for x in items:
        s = s + str(x)
    return s
"""
    assert _count(src) == 1


@pytest.mark.xfail(
    reason="concat inside a def nested in a loop runs per-call, not per-iteration",
    strict=False,
)
def test_ignores_concat_in_function_nested_in_loop():
    src = """
def f(items):
    for x in items:
        def build():
            s = ""
            s += str(x)
            return s
        build()
"""
    assert _check(src) == []


# --------------------------------------------------------------------------- #
# New adversarial coverage — compound statements wrapping an in-loop concat.   #
# The visitor recurses via generic_visit, so loop_depth stays > 0 inside any   #
# nested block and the concat must still fire.                                 #
# --------------------------------------------------------------------------- #


_WRAPPED_CONCAT_BODIES = [
    pytest.param(
        "        if x:\n            s += str(x)",
        id="if-guarded",
    ),
    pytest.param(
        "        if not x:\n            pass\n        else:\n            s += str(x)",
        id="else-guarded",
    ),
    pytest.param(
        "        try:\n            s += str(x)\n        except Exception:\n            pass",
        id="try-body",
    ),
    pytest.param(
        "        try:\n            pass\n        except Exception:\n            s += str(x)",
        id="except-body",
    ),
    pytest.param(
        "        try:\n            pass\n        finally:\n            s += str(x)",
        id="finally-body",
    ),
    pytest.param(
        "        with open('p') as _fh:\n            s += str(x)",
        id="with-body",
    ),
]


@pytest.mark.parametrize("body", _WRAPPED_CONCAT_BODIES)
def test_flags_concat_wrapped_in_compound_statement(body: str):
    src = f"""
def f(items):
    s = ""
    for x in items:
{body}
    return s
"""
    assert _count(src) == 1


def test_flags_concat_in_match_case_bodies_in_loop():
    src = """
def f(items):
    s = ""
    for x in items:
        match x:
            case 0:
                s += "zero"
            case _:
                s += str(x)
    return s
"""
    assert _count(src) == 2


def test_flags_concat_in_inner_while_in_for():
    src = """
def f(items):
    s = ""
    for x in items:
        while x:
            s += str(x)
            x -= 1
    return s
"""
    assert _count(src) == 1


def test_flags_concat_in_while_true_loop():
    src = """
def f(items):
    s = ""
    while True:
        s += str(items)
        break
    return s
"""
    assert _count(src) == 1


def test_flags_concat_over_generator_expression_iterable():
    src = """
def f(gen):
    s = ""
    for x in (i for i in gen):
        s += str(x)
    return s
"""
    assert _count(src) == 1


def test_flags_async_for_concat_when_nested_in_sync_for():
    """A pure async-for is a known gap, but the outer sync for keeps loop_depth
    positive, so the concat is still flagged."""
    src = """
async def f(rows):
    s = ""
    for row in rows:
        async for cell in row:
            s += str(cell)
    return s
"""
    assert _count(src) == 1


def test_flags_sync_for_concat_when_nested_in_async_for():
    src = """
async def f(rows):
    s = ""
    async for row in rows:
        for cell in row:
            s += str(cell)
    return s
"""
    assert _count(src) == 1


def test_flags_implicit_adjacent_string_literal_concat():
    """`"a" "b"` is parsed as a single str Constant, so it is flagged."""
    src = """
def f(items):
    s = ""
    for x in items:
        s += "a" "b"
    return s
"""
    assert _count(src) == 1


def test_allows_bytes_encode_call_in_loop():
    """`.encode()` yields bytes and is not in the string-method allowlist."""
    src = """
def f(items):
    buf = b""
    for x in items:
        buf += f"{x}".encode()
    return buf
"""
    assert _check(src) == []


def test_allows_numeric_modulo_augassign_in_loop():
    """`%` on a numeric RHS is Mod, not Add, and must not be flagged."""
    src = """
def f(items):
    total = 0
    for n in items:
        total += n % 2
    return total
"""
    assert _check(src) == []


# --------------------------------------------------------------------------- #
# New known gaps / suspected bugs — string-valued RHS shapes the heuristic     #
# fails to recognise, so the O(n^2) concat goes undetected.                    #
# --------------------------------------------------------------------------- #


@pytest.mark.xfail(
    reason="ternary IfExp RHS with two string branches is not recognised as string-ish",
    strict=True,
)
def test_flags_ternary_string_rhs_in_loop():
    src = """
def f(items, c):
    s = ""
    for x in items:
        s += "a" if c else "b"
    return s
"""
    assert _count(src) == 1


@pytest.mark.xfail(
    reason="`%`-formatting RHS is a Mod BinOp; only Add BinOps are treated as string-ish",
    strict=True,
)
def test_flags_percent_format_string_rhs_in_loop():
    src = """
def f(items):
    s = ""
    for x in items:
        s += "row %s" % x
    return s
"""
    assert _count(src) == 1


@pytest.mark.xfail(
    reason="walrus NamedExpr wrapping a string RHS is not unwrapped by the heuristic",
    strict=True,
)
def test_flags_walrus_wrapped_string_rhs_in_loop():
    src = """
def f(items):
    s = ""
    for x in items:
        s += (y := str(x))
    return s
"""
    assert _count(src) == 1
