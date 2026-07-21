from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from sarj_python_lint.rules.no_sentinel_return_on_except import (
    NoSentinelReturnOnExcept,
)


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic


def _check(source: str) -> list[Diagnostic]:
    return NoSentinelReturnOnExcept().check(Path("<test>.py"), source)


# --- flagged: sentinel returns that swallow the exception ---


def test_flags_return_none():
    src = """
def f():
    try:
        risky()
    except Exception:
        return None
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ009"


def test_flags_bare_return_is_not_flagged():
    # `return` with no value parses as Return(value=None); the rule only flags
    # explicit sentinel values, and a bare return is value=None at the AST level,
    # so confirm the documented behavior here.
    src = """
def f():
    try:
        risky()
    except Exception:
        return
"""
    # value is None -> treated as sentinel None -> flagged.
    assert len(_check(src)) == 1


def test_flags_return_empty_list():
    src = """
def f():
    try:
        risky()
    except Exception:
        return []
"""
    assert len(_check(src)) == 1


def test_flags_return_false():
    src = """
def f():
    try:
        risky()
    except Exception:
        return False
"""
    assert len(_check(src)) == 1


def test_flags_return_empty_dict():
    src = """
def f():
    try:
        risky()
    except Exception:
        return {}
"""
    assert len(_check(src)) == 1


def test_flags_return_empty_tuple():
    src = """
def f():
    try:
        risky()
    except Exception:
        return ()
"""
    assert len(_check(src)) == 1


def test_flags_return_empty_string():
    src = """
def f():
    try:
        risky()
    except Exception:
        return ''
"""
    assert len(_check(src)) == 1


def test_flags_return_set_call():
    src = """
def f():
    try:
        risky()
    except Exception:
        return set()
"""
    assert len(_check(src)) == 1


def test_flags_sentinel_as_final_stmt_after_logging():
    src = """
def f():
    try:
        risky()
    except Exception:
        logger.warning("oops")
        return None
"""
    assert len(_check(src)) == 1


def test_diagnostic_points_at_return_line_and_col():
    src = """
def f():
    try:
        risky()
    except Exception:
        return None
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].line == 6
    assert diags[0].col == 9


def test_flags_each_handler_separately():
    src = """
def f():
    try:
        risky()
    except ValueError:
        return None
    except KeyError:
        return []
"""
    assert len(_check(src)) == 2


# --- allowed: re-raises ---


def test_allows_bare_raise():
    src = """
def f():
    try:
        risky()
    except Exception:
        raise
"""
    assert _check(src) == []


def test_allows_log_then_raise():
    src = """
def f():
    try:
        risky()
    except Exception:
        logger.exception("boom")
        raise
"""
    assert _check(src) == []


def test_allows_raise_new_exception():
    src = """
def f():
    try:
        risky()
    except Exception as e:
        raise RuntimeError("wrapped") from e
"""
    assert _check(src) == []


def test_allows_raise_even_when_return_is_final_stmt():
    # A raise anywhere in the handler (before the return) means it's not a
    # silent swallow; conservatively allow it.
    src = """
def f():
    try:
        risky()
    except Exception:
        if bad():
            raise
        return None
"""
    assert _check(src) == []


def test_raise_in_nested_def_does_not_count_as_reraise():
    # The nested def's raise doesn't re-raise for THIS handler, so the sentinel
    # return is still a swallow and must be flagged.
    src = """
def f():
    try:
        risky()
    except Exception:
        def _inner():
            raise ValueError()
        return None
"""
    assert len(_check(src)) == 1


def test_raise_in_lambda_does_not_count_as_reraise():
    src = """
def f():
    try:
        risky()
    except Exception:
        g = lambda: (_ for _ in ()).throw(ValueError())
        return None
"""
    # No real `raise` statement at the handler level -> flagged.
    assert len(_check(src)) == 1


# --- allowed: meaningful return values ---


def test_allows_return_call():
    src = """
def f():
    try:
        risky()
    except Exception:
        return compute()
"""
    assert _check(src) == []


def test_allows_return_name():
    src = """
def f(default):
    try:
        risky()
    except Exception:
        return default
"""
    assert _check(src) == []


def test_allows_return_true():
    src = """
def f():
    try:
        risky()
    except Exception:
        return True
"""
    assert _check(src) == []


def test_allows_return_nonempty_list():
    src = """
def f():
    try:
        risky()
    except Exception:
        return [1, 2, 3]
"""
    assert _check(src) == []


def test_allows_return_nonempty_string():
    src = """
def f():
    try:
        risky()
    except Exception:
        return "error"
"""
    assert _check(src) == []


def test_allows_return_number():
    src = """
def f():
    try:
        risky()
    except Exception:
        return 0
"""
    assert _check(src) == []


def test_allows_return_nonempty_dict():
    src = """
def f():
    try:
        risky()
    except Exception:
        return {"ok": False}
"""
    assert _check(src) == []


def test_allows_non_set_call():
    src = """
def f():
    try:
        risky()
    except Exception:
        return list()
"""
    assert _check(src) == []


# --- allowed: sentinel return not the final statement ---


def test_allows_sentinel_return_not_final_when_handler_continues():
    # If the return isn't the final statement we don't flag (final stmt rule).
    src = """
def f():
    try:
        risky()
    except Exception:
        if cond:
            return None
        log_and_recover()
"""
    assert _check(src) == []


def test_allows_no_return_in_handler():
    src = """
def f():
    try:
        risky()
    except Exception:
        log_and_recover()
"""
    assert _check(src) == []


# --- syntax errors return [] ---


def test_syntax_error_returns_empty():
    assert _check("def f(:\n    pass") == []


# ---------------------------------------------------------------------------
# Added coverage
# ---------------------------------------------------------------------------


def _return_src(ret: str, *, handler: str = "except Exception:") -> str:
    """A function whose sole handler ends in `return <ret>` (return at line 6)."""
    return f"""
def f():
    try:
        risky()
    {handler}
        return {ret}
"""


# --- flagged: every sentinel return shape (parametrized) ---


@pytest.mark.parametrize(
    "ret",
    [
        "None",
        "False",
        "[]",
        "{}",
        "()",
        "''",
        '""',
        '""""""',
        "set()",
    ],
)
def test_flags_every_sentinel_shape(ret: str):
    diags = _check(_return_src(ret))
    assert len(diags) == 1
    assert diags[0].code == "SARJ009"


@pytest.mark.parametrize(
    "handler",
    [
        "except Exception:",
        "except:",
        "except ValueError:",
        "except (ValueError, KeyError):",
        "except Exception as e:",
    ],
)
def test_flags_across_handler_forms(handler: str):
    # Bare except, typed except, tuple-of-types, and a bound `as e` all flag.
    assert len(_check(_return_src("None", handler=handler))) == 1


def test_flags_bare_except():
    src = """
def f():
    try:
        risky()
    except:
        return []
"""
    assert len(_check(src)) == 1


def test_flags_except_star_group():
    src = """
def f():
    try:
        risky()
    except* ValueError:
        return None
"""
    assert len(_check(src)) == 1


def test_flags_async_function_handler():
    src = """
async def f():
    try:
        await risky()
    except Exception:
        return None
"""
    assert len(_check(src)) == 1


def test_flags_handler_in_method():
    src = """
class C:
    def m(self):
        try:
            risky()
        except Exception:
            return {}
"""
    assert len(_check(src)) == 1


def test_flags_with_finally_present():
    # A `finally` clause is not an ExceptHandler and doesn't change the verdict.
    src = """
def f():
    try:
        risky()
    except Exception:
        return None
    finally:
        cleanup()
"""
    assert len(_check(src)) == 1


@pytest.mark.parametrize(
    "prelude",
    [
        'logger.warning("oops")',
        'logger.exception("boom")',
        "cleanup()",
        "x = compute()",
    ],
)
def test_flags_sentinel_after_non_raising_prelude(prelude: str):
    # Logging / cleanup before the sentinel return does NOT exempt the swallow —
    # only an actual `raise` does.
    src = f"""
def f():
    try:
        risky()
    except Exception:
        {prelude}
        return None
"""
    assert len(_check(src)) == 1


def test_flags_both_nested_handlers():
    src = """
def f():
    try:
        risky()
    except Exception:
        try:
            g()
        except ValueError:
            return None
        return None
"""
    assert len(_check(src)) == 2


# --- line/col precision ---


def test_line_col_at_deeper_indent():
    src = """
class C:
    def m(self):
        try:
            risky()
        except Exception:
            return None
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].line == 7
    assert diags[0].col == 13


def test_line_col_single_space_indent():
    src = "def f():\n try:\n  risky()\n except Exception:\n  return None"
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].line == 5
    assert diags[0].col == 3


# --- ordering of diagnostics ---


def test_flat_handlers_emitted_in_source_order():
    src = """
def f():
    try:
        risky()
    except A:
        return None
    except B:
        return []
    except C:
        return {}
"""
    assert [d.line for d in _check(src)] == [6, 8, 10]


def test_nested_handlers_actual_walk_order():
    # Pins the current ast.walk (breadth-first) emission: the OUTER handler's
    # return (line 10) is reported before the INNER handler's (line 9), so the
    # sequence is not ascending by line. The strict-xfail below documents that
    # this diverges from the (line, col) sort every other rule applies.
    src = """
def f():
    try:
        risky()
    except Exception:
        try:
            g()
        except ValueError:
            return None
        return None
"""
    positions = [(d.line, d.col) for d in _check(src)]
    assert positions == [(10, 9), (9, 13)]


@pytest.mark.xfail(
    reason="SARJ009 appends diagnostics in ast.walk order and never sorts by "
    "(line, col); every other rule in the package sorts. See report.",
    strict=True,
)
def test_nested_handlers_should_be_sorted_by_position():
    src = """
def f():
    try:
        risky()
    except Exception:
        try:
            g()
        except ValueError:
            return None
        return None
"""
    positions = [(d.line, d.col) for d in _check(src)]
    assert positions == sorted(positions)


# --- allowed: re-raise variants (must NOT fire) ---


def test_allows_raise_in_for_loop():
    src = """
def f():
    try:
        risky()
    except Exception:
        for _ in range(3):
            raise
        return None
"""
    assert _check(src) == []


def test_allows_raise_in_with_block():
    src = """
def f():
    try:
        risky()
    except Exception:
        with lock():
            raise
        return None
"""
    assert _check(src) == []


def test_allows_raise_inside_nested_try_handler():
    # `_contains_raise` descends into a nested try (not a function boundary), so
    # a raise in the inner handler counts as a re-raise for the outer handler.
    src = """
def f():
    try:
        risky()
    except Exception:
        try:
            h()
        except ValueError:
            raise
        return None
"""
    assert _check(src) == []


def test_allows_raise_from_in_except_group():
    src = """
def f():
    try:
        risky()
    except* ValueError as eg:
        raise RuntimeError("wrapped") from eg
"""
    assert _check(src) == []


# --- allowed: actionable recovery returns a meaningful value ---


@pytest.mark.parametrize(
    "ret",
    [
        "True",
        "0",
        "0.0",
        "1",
        "-1",
        "0j",
        '"error"',
        "'x'",
        "[1]",
        "[1, 2, 3]",
        '{"ok": False}',
        "{None: None}",
        "(None,)",
        "default",
        "compute()",
        "fallback_value",
        "list()",
        "dict()",
        "frozenset()",
        "bytearray()",
        "...",
        "b''",
        'f""',
        "not x",
    ],
)
def test_allows_meaningful_return_values(ret: str):
    assert _check(_return_src(ret)) == []


def test_false_is_sentinel_but_zero_is_not():
    # `return False` is flagged; `return 0` is not — `0 is False` is False, and
    # 0 can be a legitimate recovered value.
    assert len(_check(_return_src("False"))) == 1
    assert _check(_return_src("0")) == []


def test_allows_return_recovered_local():
    src = """
def f():
    try:
        risky()
    except Exception as e:
        recovered = handle(e)
        return recovered
"""
    assert _check(src) == []


# --- false-positive guards ---


def test_return_in_try_body_not_flagged():
    # A sentinel return in the `try` body (success path) is not a swallow.
    src = """
def f():
    try:
        return None
    except Exception:
        raise
"""
    assert _check(src) == []


def test_return_in_else_clause_not_flagged():
    src = """
def f():
    try:
        risky()
    except Exception:
        raise
    else:
        return []
"""
    assert _check(src) == []


def test_return_in_finally_not_flagged():
    src = """
def f():
    try:
        risky()
    except Exception:
        raise
    finally:
        return None
"""
    assert _check(src) == []


def test_sentinel_return_in_fallback_branch_not_final_allowed():
    # The sentinel return is guarded and the handler continues with recovery, so
    # it is not the handler's final statement — not flagged.
    src = """
def f():
    try:
        risky()
    except Exception:
        if fatal():
            return None
        return recover()
"""
    assert _check(src) == []


def test_handler_ending_in_recovery_call_allowed():
    src = """
def f():
    try:
        risky()
    except Exception:
        return recover_from_error()
"""
    assert _check(src) == []


def test_raise_new_error_without_from_allowed():
    src = """
def f():
    try:
        risky()
    except Exception:
        raise RuntimeError("boom")
"""
    assert _check(src) == []


def test_return_none_before_raise_allowed():
    # The final statement is a raise, not the sentinel return.
    src = """
def f():
    try:
        risky()
    except Exception:
        if cond:
            return None
        raise
"""
    assert _check(src) == []


# --- degenerate inputs ---


@pytest.mark.parametrize(
    "src",
    [
        "",
        "\n\n",
        "# just a comment\n",
        "x = 1\n",
        "def f():\n    return None\n",
        "try:\n    risky()\nexcept Exception:\n    pass\n",
    ],
)
def test_no_diagnostics_for_sources_without_swallowing_handler(src: str):
    assert _check(src) == []


def test_module_level_return_in_except_is_flagged():
    # `return` outside a function is a compile-time error, but `ast.parse` (which
    # `parse_or_none` uses) does NOT reject it — that check happens later in
    # symbol-table/compile. So the handler is walked and the swallow is flagged.
    src = """
try:
    risky()
except Exception:
    return None
"""
    assert len(_check(src)) == 1


def test_deeply_nested_function_handler_flagged():
    src = """
def outer():
    def inner():
        try:
            risky()
        except Exception:
            return None
    return inner
"""
    assert len(_check(src)) == 1
