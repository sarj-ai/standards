from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sarj_sql_lint.rules.index_concurrently import IndexConcurrently


if TYPE_CHECKING:
    from sarj_sql_lint.rule_base import Diagnostic


def _check(source: str) -> list[Diagnostic]:
    return IndexConcurrently().check(Path("migration.sql"), source)


def test_flags_create_index_without_concurrently():
    src = "CREATE INDEX idx_orders_user ON orders(user_id);"
    diags = _check(src)
    assert len(diags) == 1
    assert "CONCURRENTLY" in diags[0].message


def test_flags_create_unique_index_without_concurrently():
    src = "CREATE UNIQUE INDEX idx_orders_user ON orders(user_id);"
    assert len(_check(src)) == 1


def test_flags_create_index_if_not_exists_without_concurrently():
    src = "CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);"
    assert len(_check(src)) == 1


def test_allows_create_index_concurrently():
    src = "CREATE INDEX CONCURRENTLY idx_orders_user ON orders(user_id);"
    assert _check(src) == []


def test_allows_create_unique_index_concurrently_if_not_exists():
    src = "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_u ON orders(user_id);"
    assert _check(src) == []


def test_is_case_insensitive():
    src = "create index idx_orders_user on orders(user_id);"
    assert len(_check(src)) == 1


def test_ignores_drop_index():
    src = "DROP INDEX CONCURRENTLY IF EXISTS idx_orders_user;"
    assert _check(src) == []


def test_skips_comment_lines():
    src = """
-- CREATE INDEX idx ON orders(user_id);
/* CREATE INDEX idx2 ON orders(note); */
"""
    assert _check(src) == []
