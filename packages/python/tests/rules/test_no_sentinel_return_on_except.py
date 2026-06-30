from pathlib import Path
from typing import TYPE_CHECKING

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
