from pathlib import Path

from sarj_sql_lint.rule_base import Diagnostic
from sarj_sql_lint.rules.idempotent_ddl import IdempotentDdl


def _check(source: str) -> list[Diagnostic]:
    return IdempotentDdl().check(Path("migration.sql"), source)


def test_flags_create_table_without_if_not_exists():
    src = "CREATE TABLE orders (id BIGSERIAL PRIMARY KEY);"
    assert len(_check(src)) == 1


def test_allows_create_table_if_not_exists():
    src = "CREATE TABLE IF NOT EXISTS orders (id BIGSERIAL PRIMARY KEY);"
    assert _check(src) == []


def test_flags_add_column_without_if_not_exists():
    src = "ALTER TABLE orders ADD COLUMN note TEXT;"
    assert len(_check(src)) == 1


def test_allows_add_column_if_not_exists():
    src = "ALTER TABLE orders ADD COLUMN IF NOT EXISTS note TEXT;"
    assert _check(src) == []


def test_flags_create_index_without_if_not_exists():
    src = "CREATE INDEX idx_orders_user ON orders(user_id);"
    assert len(_check(src)) == 1


def test_flags_create_unique_index_without_if_not_exists():
    src = "CREATE UNIQUE INDEX idx_orders_user ON orders(user_id);"
    assert len(_check(src)) == 1


def test_allows_create_index_if_not_exists():
    src = "CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);"
    assert _check(src) == []


def test_allows_create_index_concurrently_if_not_exists():
    src = "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_u ON orders(user_id);"
    assert _check(src) == []


def test_flags_drop_table_without_if_exists():
    src = "DROP TABLE orders;"
    assert len(_check(src)) == 1


def test_flags_drop_index_without_if_exists():
    src = "DROP INDEX idx_orders_user;"
    assert len(_check(src)) == 1


def test_allows_drop_with_if_exists():
    src = """
DROP TABLE IF EXISTS orders;
DROP INDEX IF EXISTS idx_orders_user;
DROP INDEX CONCURRENTLY IF EXISTS idx_orders_user;
"""
    assert _check(src) == []


def test_is_case_insensitive():
    src = "create table orders (id bigserial primary key);"
    assert len(_check(src)) == 1


def test_flags_each_violation_in_multi_statement_file():
    src = """
CREATE TABLE orders (id BIGSERIAL PRIMARY KEY);
ALTER TABLE orders ADD COLUMN note TEXT;
CREATE INDEX idx_orders_note ON orders(note);
DROP TABLE legacy_orders;
"""
    assert len(_check(src)) == 4


def test_skips_comment_lines():
    src = """
-- CREATE TABLE orders was dropped here; DROP TABLE orders too
/* CREATE INDEX idx ON orders(user_id); */
CREATE TABLE IF NOT EXISTS orders (id BIGSERIAL PRIMARY KEY);
"""
    assert _check(src) == []
