from pathlib import Path

from sarj_python_lint.rule_base import is_suppressed
from sarj_python_lint.rules.store_insert_requires_on_conflict import (
    StoreInsertRequiresOnConflict,
)


def _check(source: str) -> list:
    return StoreInsertRequiresOnConflict().check(Path("foo_store.py"), source)


def test_flags_bare_insert_values_in_execute():
    src = 'await cur.execute("INSERT INTO task (id) VALUES (%s)", (task_id,))'
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ018"
    assert "upsert" in diags[0].message.lower()


def test_flags_multiline_triple_quoted_insert():
    src = '''
async def create(self):
    await cur.execute(
        SQL("""
        INSERT INTO task (organization_id, status)
        VALUES (%s, %s)
        RETURNING id
        """).format(),
        (org_id, status),
    )
'''
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].line == 4


def test_allows_insert_with_on_conflict():
    src = '''
await cur.execute(SQL("""
    INSERT INTO organization (id, name)
    VALUES (%s, %s)
    ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
    RETURNING id
"""))
'''
    assert _check(src) == []


def test_allows_insert_with_on_conflict_do_nothing():
    src = 'q = "INSERT INTO t (id) VALUES (%s) ON CONFLICT DO NOTHING"'
    assert _check(src) == []


def test_ignores_select_only_query():
    src = 'await cur.execute("SELECT id FROM task WHERE id = %s", (x,))'
    assert _check(src) == []


def test_ignores_returning_select_without_insert():
    src = 'q = "WITH x AS (SELECT 1) SELECT * FROM task"'
    assert _check(src) == []


def test_flags_insert_select_write():
    src = 'q = "INSERT INTO archive (id) SELECT id FROM task WHERE done"'
    diags = _check(src)
    assert len(diags) == 1


def test_on_conflict_in_sql_comment_does_not_excuse():
    src = '''q = """
    INSERT INTO t (id) VALUES (%s)
    -- ON CONFLICT (id) DO NOTHING would go here
    """'''
    assert len(_check(src)) == 1


def test_insert_in_sql_comment_does_not_trigger():
    src = '''q = """
    SELECT id FROM t
    -- INSERT INTO t (id) VALUES (1)
    """'''
    assert _check(src) == []


def test_insert_in_block_comment_does_not_trigger():
    src = 'q = "/* INSERT INTO t (id) VALUES (1) */ SELECT 1 FROM t"'
    assert _check(src) == []


def test_concatenated_string_keeps_insert_and_on_conflict_together():
    src = """q = (
    "INSERT INTO t (id) VALUES (%s) "
    "ON CONFLICT (id) DO NOTHING"
)"""
    assert _check(src) == []


def test_explicit_plus_concatenation_is_flagged_when_no_on_conflict():
    src = 'q = "INSERT INTO t (id) " + "VALUES (%s)"'
    diags = _check(src)
    assert len(diags) == 1


def test_case_insensitive():
    src = 'q = "insert into t (id) values (%s)"'
    assert len(_check(src)) == 1


def test_suppressed_by_sarj_noqa():
    src = 'q = "INSERT INTO ch_events (id) VALUES (%s)"  # sarj-noqa: SARJ018 — ClickHouse has no upsert'

    diags = _check(src)
    assert len(diags) == 1
    assert is_suppressed(src.splitlines(), diags[0].line, diags[0].code)


def test_each_insert_flagged_separately():
    src = """
a = "INSERT INTO t (id) VALUES (1)"
b = "INSERT INTO u (id) VALUES (2)"
"""
    assert len(_check(src)) == 2


def test_syntax_error_returns_empty():
    assert _check("def (:::") == []
