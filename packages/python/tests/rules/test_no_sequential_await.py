from pathlib import Path
from typing import TYPE_CHECKING

from sarj_python_lint.rules.no_sequential_await import NoSequentialAwait


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic


def _check(source: str, path: str = "<prod>.py") -> list[Diagnostic]:
    return NoSequentialAwait().check(Path(path), source)


_SEQUENTIAL_LOOP = """
async def f(items):
    for x in items:
        result = await call(x)
"""


def test_skips_test_prefixed_files():
    assert _check(_SEQUENTIAL_LOOP, "test_call_store.py") == []


def test_skips_files_under_tests_dir():
    assert _check(_SEQUENTIAL_LOOP, "python/bulbul/tests/stores/seed.py") == []


def test_skips_conftest():
    assert _check(_SEQUENTIAL_LOOP, "tests/conftest.py") == []


def test_still_flags_production_files():
    assert len(_check(_SEQUENTIAL_LOOP, "python/bulbul/bulbul/calls/call_store.py")) == 1


def test_flags_sequential_await():
    src = """
async def f(items):
    for x in items:
        result = await call(x)
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ001"


def test_allows_async_for_with_no_await_in_body():
    src = """
async def f(stream):
    async for chunk in stream:
        process(chunk)
"""
    assert _check(src) == []


def test_allows_gather_pattern():
    src = """
import asyncio

async def f(items):
    await asyncio.gather(*[call(x) for x in items])
"""
    assert _check(src) == []


def test_allows_await_outside_loop():
    src = """
async def f():
    x = await call()
"""
    assert _check(src) == []


def test_one_diagnostic_per_loop_not_per_await():
    """Multi-await loops emit a single diagnostic to avoid noise."""
    src = """
async def f(items):
    for x in items:
        a = await one(x)
        b = await two(x)
"""
    assert len(_check(src)) == 1


def test_flags_sequential_await_in_while():
    src = """
async def f(q):
    while not q.empty():
        item = await q.get()
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ001"


def test_flags_await_in_comprehension():
    src = """
async def f(items):
    return [await call(x) for x in items]
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ001"


def test_flags_await_in_generator_expression():
    src = """
async def f(items):
    return any(await ok(x) for x in items)
"""
    assert len(_check(src)) == 1


def test_flags_each_distinct_loop_once():
    src = """
async def f(rows, cols):
    for r in rows:
        a = await one(r)
    while cols:
        b = await two(cols.pop())
"""
    assert len(_check(src)) == 2


def test_does_not_escape_nested_function_boundary():
    """A loop in an outer function must not claim an await in a nested def."""
    src = """
async def outer(items):
    for x in items:
        def inner():
            return helper()

    async def sibling():
        return await call()
"""
    assert _check(src) == []


def test_nested_loops_flag_only_inner():
    src = """
async def f(matrix):
    for row in matrix:
        for cell in row:
            v = await load(cell)
"""
    assert len(_check(src)) == 1
