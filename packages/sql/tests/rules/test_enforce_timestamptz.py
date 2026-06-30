from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sarj_sql_lint.rules.enforce_timestamptz import EnforceTimestamptz


if TYPE_CHECKING:
    from sarj_sql_lint.rule_base import Diagnostic


def _check(source: str) -> list[Diagnostic]:
    return EnforceTimestamptz().check(Path("migration.sql"), source)


def test_flags_naive_timestamp():
    src = """
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL
);
"""
    assert len(_check(src)) == 1


def test_allows_timestamp_with_time_zone():
    src = """
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
"""
    assert _check(src) == []


def test_allows_timestamptz_keyword():
    src = """
CREATE TABLE orders (
    created_at TIMESTAMPTZ NOT NULL
);
"""
    assert _check(src) == []


def test_allows_timestamp_with_precision_and_time_zone():
    src = "created_at TIMESTAMP(3) WITH TIME ZONE NOT NULL"
    assert _check(src) == []


def test_flags_timestamp_with_precision_but_no_time_zone():
    src = "created_at TIMESTAMP(6) NOT NULL"
    assert len(_check(src)) == 1


def test_skips_comment_lines():
    src = """
-- TIMESTAMP without WITH TIME ZONE is forbidden in our docs comments
CREATE TABLE x (created_at TIMESTAMPTZ);
"""
    assert _check(src) == []


def test_skips_trailing_inline_comment():
    src = "created_at TIMESTAMPTZ NOT NULL -- TIMESTAMP was the old type"
    assert _check(src) == []


def test_skips_string_literal_body():
    src = "INSERT INTO log (kind) VALUES ('TIMESTAMP');"
    assert _check(src) == []


def test_skips_block_comment_body():
    src = """
/*
  legacy column was TIMESTAMP without zone
*/
CREATE TABLE x (created_at TIMESTAMPTZ);
"""
    assert _check(src) == []
