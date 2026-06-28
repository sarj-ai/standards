from pathlib import Path

from sarj_python_lint.rules.prefer_class_row import PreferClassRow


def _check(source: str, path: str = "<t>.py") -> list:
    return PreferClassRow().check(Path(path), source)


def test_flags_dict_row_on_cursor():
    src = """
from psycopg.rows import dict_row

async def get(conn):
    async with conn.cursor(row_factory=dict_row) as cur:
        return await cur.fetchone()
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ013"


def test_flags_attribute_access_dict_row():
    src = """
import psycopg

def get(conn):
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        return cur.fetchone()
"""
    assert len(_check(src)) == 1


def test_flags_connection_level_dict_row():
    src = """
from psycopg.rows import dict_row

def connect():
    return psycopg.connect(dsn, row_factory=dict_row)
"""
    assert len(_check(src)) == 1


def test_flags_multiple_cursors():
    src = """
from psycopg.rows import dict_row

async def store(conn):
    async with conn.cursor(row_factory=dict_row) as a:
        pass
    async with conn.cursor(row_factory=dict_row) as b:
        pass
"""
    assert len(_check(src)) == 2


def test_allows_class_row():
    src = """
from psycopg.rows import class_row

async def get(conn):
    async with conn.cursor(row_factory=class_row(Task)) as cur:
        return await cur.fetchone()
"""
    assert _check(src) == []


def test_allows_tuple_row():
    src = """
from psycopg.rows import tuple_row

def get(conn):
    with conn.cursor(row_factory=tuple_row) as cur:
        return cur.fetchone()
"""
    assert _check(src) == []


def test_ignores_unrelated_keyword_named_dict_row_value():
    src = """
def configure(dict_row):
    return helper(parser=dict_row)
"""
    assert _check(src) == []


def test_ignores_syntax_error():
    assert _check("def broken(:\n") == []
