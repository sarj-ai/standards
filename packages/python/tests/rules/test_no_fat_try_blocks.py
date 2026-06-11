from pathlib import Path

from sarj_python_lint.rules.no_fat_try_blocks import NoFatTryBlocks


def _check(source: str) -> list:
    return NoFatTryBlocks().check(Path("<t>.py"), source)


def test_flags_try_with_four_statements():
    src = """
try:
    a = 1
    b = 2
    c = 3
    d = 4
except ValueError:
    pass
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ007"
    assert diags[0].line == 2


def test_allows_try_with_exactly_three_statements():
    src = """
try:
    a = 1
    b = 2
    c = 3
except ValueError:
    pass
"""
    assert _check(src) == []


def test_allows_skinny_try():
    src = """
try:
    result = risky()
except ValueError:
    result = None
"""
    assert _check(src) == []


def test_nested_try_counted_independently():
    """Outer try has 1 statement (the inner try); only the inner is fat."""
    src = """
try:
    try:
        a = 1
        b = 2
        c = 3
        d = 4
    except KeyError:
        pass
except ValueError:
    pass
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].line == 3


def test_both_nested_and_outer_flagged_when_both_fat():
    src = """
try:
    a = 1
    b = 2
    c = 3
    try:
        w = 1
        x = 2
        y = 3
        z = 4
    except KeyError:
        pass
except ValueError:
    pass
"""
    diags = _check(src)
    assert len(diags) == 2


def test_if_block_inside_try_counts_as_one_statement():
    """Only top-level body length matters; statements inside an `if` don't count."""
    src = """
try:
    a = 1
    if a:
        b = 2
        c = 3
        d = 4
        e = 5
    f = 6
except ValueError:
    pass
"""
    assert _check(src) == []


def test_flags_fat_try_in_async_function():
    src = """
async def handler():
    try:
        a = await one()
        b = await two()
        c = await three()
        d = await four()
    except ValueError:
        pass
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ007"


def test_flags_fat_try_star():
    src = """
try:
    a = 1
    b = 2
    c = 3
    d = 4
except* ValueError:
    pass
"""
    diags = _check(src)
    assert len(diags) == 1


def test_finally_and_else_bodies_not_counted():
    src = """
try:
    a = 1
except ValueError:
    pass
else:
    b = 2
    c = 3
    d = 4
    e = 5
finally:
    f = 6
    g = 7
    h = 8
    i = 9
"""
    assert _check(src) == []


def test_syntax_error_returns_empty():
    assert _check("def broken(:\n    pass") == []
