from pathlib import Path
from typing import TYPE_CHECKING

from sarj_python_lint.rules.no_fat_try_blocks import NoFatTryBlocks


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic


def _check(source: str) -> list[Diagnostic]:
    return NoFatTryBlocks().check(Path("<t>.py"), source)


def test_flags_try_with_four_throwing_statements():
    src = """
try:
    a = one()
    b = two()
    c = three()
    d = four()
except ValueError:
    pass
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ007"
    assert diags[0].line == 2


def test_allows_try_with_exactly_three_throwing_statements():
    src = """
try:
    a = one()
    b = two()
    c = three()
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


def test_plain_assignments_do_not_count():
    """A body of only non-throwing rebinds has no statement to isolate."""
    src = """
try:
    self.a = 1
    self.b = self.a
    self.c = 2
    self.d = other
    self.e = 3
except ValueError:
    raise
"""
    assert _check(src) == []


def test_non_throwing_statements_are_free_around_one_call():
    src = """
try:
    a = 1
    b = 2
    c = 3
    d = risky()
except ValueError:
    pass
"""
    assert _check(src) == []


def test_else_clause_exempts_the_block():
    src = """
try:
    a = one()
    b = two()
    c = three()
    d = four()
except ValueError:
    pass
else:
    use(a, b, c, d)
"""
    assert _check(src) == []


def test_finally_clause_exempts_the_block():
    src = """
try:
    a = one()
    b = two()
    c = three()
    d = four()
finally:
    cleanup()
"""
    assert _check(src) == []


def test_nested_try_counted_independently():
    """Outer try has 1 throwing statement (the inner try); only the inner is fat."""
    src = """
try:
    try:
        a = one()
        b = two()
        c = three()
        d = four()
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
    a = one()
    b = two()
    c = three()
    d = four()
    try:
        w = five()
        x = six()
        y = seven()
        z = eight()
    except KeyError:
        pass
except ValueError:
    pass
"""
    diags = _check(src)
    assert len(diags) == 2


def test_compound_statement_inside_try_counts_as_one():
    """A throwing `if` is one statement, not its inner statement count."""
    src = """
try:
    a = load()
    if cond():
        b = build()
        c = extend(b)
        d = persist(c)
        e = log(d)
    f = save()
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
    a = one()
    b = two()
    c = three()
    d = four()
except* ValueError:
    pass
"""
    diags = _check(src)
    assert len(diags) == 1


def test_syntax_error_returns_empty():
    assert _check("def broken(:\n    pass") == []
