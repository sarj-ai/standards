from pathlib import Path

from sarj_sql_lint.rule_base import Diagnostic
from sarj_sql_lint.rules.prefer_text_over_varchar import PreferTextOverVarchar


def _check(source: str) -> list[Diagnostic]:
    return PreferTextOverVarchar().check(Path("migration.sql"), source)


def test_flags_varchar_with_length():
    src = "CREATE TABLE IF NOT EXISTS u (name VARCHAR(255) NOT NULL);"
    diags = _check(src)
    assert len(diags) == 1
    assert "TEXT" in diags[0].message


def test_flags_character_varying_with_length():
    src = "ALTER TABLE u ADD COLUMN IF NOT EXISTS bio CHARACTER VARYING(1024);"
    assert len(_check(src)) == 1


def test_is_case_insensitive_and_tolerates_spacing():
    src = "name varchar (64) not null"
    assert len(_check(src)) == 1


def test_flags_each_occurrence():
    src = """
CREATE TABLE IF NOT EXISTS u (
    first_name VARCHAR(50),
    last_name VARCHAR(50)
);
"""
    assert len(_check(src)) == 2


def test_allows_text():
    src = """
CREATE TABLE IF NOT EXISTS u (
    name TEXT NOT NULL CHECK (char_length(name) <= 255)
);
"""
    assert _check(src) == []


def test_allows_bare_varchar_identifier_substrings():
    src = "SELECT my_varchar(255) FROM helper_functions"
    assert _check(src) == []


def test_skips_comment_lines():
    src = """
-- VARCHAR(255) is forbidden; use TEXT
/* CHARACTER VARYING(10) too */
"""
    assert _check(src) == []
