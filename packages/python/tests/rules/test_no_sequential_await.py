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


# --- iterable is evaluated once, not per element (former false positives) ---


def test_allows_await_in_comprehension_iterable():
    """`{x for x in await fetch()}` awaits once to build the iterable."""
    src = """
async def f():
    return {row.id: row for row in await store.fetch_all()}
"""
    assert _check(src) == []


def test_allows_await_in_for_iterable():
    src = """
async def f():
    for trunk in (await client.list_trunks()).rules:
        register(trunk)
"""
    assert _check(src) == []


def test_allows_await_in_genexp_and_listcomp_iterable():
    src = """
async def f():
    a = [x for x in await one()]
    b = list(y for y in await two())
    return a, b
"""
    assert _check(src) == []


def test_still_flags_await_in_element_even_with_awaited_iterable():
    """The iterable await is free, but a per-element await is still flagged."""
    src = """
async def f():
    return [await enrich(x) for x in await fetch()]
"""
    assert len(_check(src)) == 1


def test_still_flags_await_in_for_body_when_iter_also_awaits():
    src = """
async def f():
    for x in await fetch():
        await process(x)
"""
    assert len(_check(src)) == 1


def test_flags_awaited_iterable_of_inner_loop_nested_in_outer():
    """Inner loop's iterable awaits once per outer element — that is sequential."""
    src = """
async def f(groups):
    for g in groups:
        for item in await load(g):
            use(item)
"""
    assert len(_check(src)) == 1


def test_allows_await_in_condition_is_still_flagged():
    """An await in a comprehension `if` runs per element — still flagged."""
    src = """
async def f(items):
    return [x for x in items if await ok(x)]
"""
    assert len(_check(src)) == 1


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
