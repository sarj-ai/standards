from pathlib import Path

from sarj_sql_lint.rule_base import Diagnostic
from sarj_sql_lint.rules.insert_requires_on_conflict import InsertRequiresOnConflict


def _check(source: str) -> list[Diagnostic]:
    return InsertRequiresOnConflict().check(Path("migration.sql"), source)


def test_flags_bare_insert():
    src = "INSERT INTO plan (name) VALUES ('free');"
    diags = _check(src)
    assert len(diags) == 1
    assert "ON CONFLICT" in diags[0].message


def test_allows_insert_with_on_conflict_same_line():
    src = "INSERT INTO plan (name) VALUES ('free') ON CONFLICT (name) DO NOTHING;"
    assert _check(src) == []


def test_allows_multiline_insert_with_on_conflict_later_in_statement():
    src = """
INSERT INTO plan (name, price)
VALUES
    ('free', 0),
    ('pro', 99)
ON CONFLICT (name)
DO UPDATE SET price = EXCLUDED.price;
"""
    assert _check(src) == []


def test_flags_multiline_insert_without_on_conflict():
    src = """
INSERT INTO plan (name, price)
VALUES
    ('free', 0),
    ('pro', 99);
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].line == 2


def test_on_conflict_in_next_statement_does_not_excuse_previous():
    src = """
INSERT INTO plan (name) VALUES ('free');
INSERT INTO plan (name) VALUES ('pro') ON CONFLICT (name) DO NOTHING;
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].line == 2


def test_flags_each_bare_insert_statement():
    src = """
INSERT INTO plan (name) VALUES ('free');
INSERT INTO plan (name) VALUES ('pro');
"""
    assert len(_check(src)) == 2


def test_on_conflict_in_trailing_comment_does_not_count():
    src = "INSERT INTO plan (name) VALUES ('free'); -- TODO add ON CONFLICT"
    assert len(_check(src)) == 1


def test_skips_pure_comment_lines():
    src = """
-- INSERT INTO plan must always be an upsert;
/* not a real statement */
"""
    assert _check(src) == []


def test_is_case_insensitive():
    src = """
insert into plan (name)
values ('free')
on conflict (name) do nothing;
"""
    assert _check(src) == []


def test_statement_without_trailing_semicolon_is_still_checked():
    src = "INSERT INTO plan (name) VALUES ('free')"
    assert len(_check(src)) == 1
