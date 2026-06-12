from pathlib import Path

from sarj_python_lint.rules.try_block_too_large import TryBlockTooLarge


def _check(source: str) -> list:
    return TryBlockTooLarge().check(Path("<test>.py"), source)


def test_flags_try_with_four_body_statements():
    src = """
def f():
    try:
        a = 1
        b = 2
        c = 3
        d = 4
    except Exception:
        pass
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ009"


def test_allows_try_with_max_statements():
    src = """
def f():
    try:
        a = 1
        b = 2
        c = 3
    except Exception:
        pass
"""
    assert _check(src) == []


def test_allows_try_with_fewer_than_max_statements():
    src = """
def f():
    try:
        risky()
    except Exception:
        pass
"""
    assert _check(src) == []


def test_only_body_counts_large_handler_allowed():
    """A small try body with a large except handler is allowed."""
    src = """
def f():
    try:
        risky()
    except Exception:
        a = 1
        b = 2
        c = 3
        d = 4
        e = 5
"""
    assert _check(src) == []


def test_only_body_counts_large_orelse_and_finally_allowed():
    """Large `else` and `finally` blocks do not count toward the body limit."""
    src = """
def f():
    try:
        risky()
    except Exception:
        pass
    else:
        a = 1
        b = 2
        c = 3
        d = 4
    finally:
        x = 1
        y = 2
        z = 3
        w = 4
"""
    assert _check(src) == []


def test_does_not_recurse_into_nested_statements():
    """Only direct elements of node.body are counted, not nested statements."""
    src = """
def f():
    try:
        if cond:
            a = 1
            b = 2
            c = 3
            d = 4
    except Exception:
        pass
"""
    assert _check(src) == []


def test_syntax_error_returns_empty():
    src = "def f(:\n    pass\n"
    assert _check(src) == []
