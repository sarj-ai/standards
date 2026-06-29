from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sarj_sql_lint.rules.no_limit_offset import NoLimitOffset


if TYPE_CHECKING:
    from sarj_sql_lint.rule_base import Diagnostic


def _check(source: str) -> list[Diagnostic]:
    return NoLimitOffset().check(Path("query.sql"), source)


def test_flags_offset():
    src = "SELECT * FROM call ORDER BY id LIMIT 50 OFFSET 100;"
    diags = _check(src)
    assert len(diags) == 1
    assert "cursor" in diags[0].message


def test_is_case_insensitive():
    src = "select * from call order by id limit 50 offset 100;"
    assert len(_check(src)) == 1


def test_allows_cursor_pagination():
    src = "SELECT * FROM call WHERE id > :cursor ORDER BY id LIMIT 50;"
    assert _check(src) == []


def test_allows_offset_substring_identifiers():
    src = "SELECT utc_offset, byte_offset_end FROM tz_info"
    assert _check(src) == []


def test_allows_quoted_offset_identifier():
    src = 'SELECT "offset" FROM tz_info ORDER BY id'
    assert _check(src) == []


def test_skips_comment_lines():
    src = """
-- OFFSET is forbidden, use cursor pagination
/* LIMIT 10 OFFSET 20 */
SELECT * FROM call WHERE id > :cursor ORDER BY id LIMIT 50;
"""
    assert _check(src) == []


def test_skips_offset_inside_string_literal():
    src = "INSERT INTO doc (body) VALUES ('use OFFSET sparingly');"
    assert _check(src) == []
