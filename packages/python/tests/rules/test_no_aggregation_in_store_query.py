from pathlib import Path

from sarj_python_lint.rule_base import is_suppressed
from sarj_python_lint.rules.no_aggregation_in_store_query import (
    NoAggregationInStoreQuery,
)


def _check(source: str) -> list:
    return NoAggregationInStoreQuery().check(Path("call_store.py"), source)


def test_ignores_prose_with_distinct_and_from():
    # A docstring/LLM-prompt string with "distinct"/"from"/"count(" as English is
    # not a SQL query (no SELECT ... FROM / UPDATE ... SET shape).
    src = 'msg = "This failure is distinct from the others reported by the runner."\n'
    assert _check(src) == []


def test_flags_count():
    diags = _check('q = "SELECT COUNT(*) FROM call"\n')
    assert len(diags) == 1
    assert "COUNT(" in diags[0].message


def test_flags_group_by():
    assert len(_check('q = "SELECT status, count(*) FROM call GROUP BY status"\n')) == 1


def test_flags_distinct():
    diags = _check('q = "SELECT DISTINCT org_id FROM call"\n')
    assert len(diags) == 1
    assert "DISTINCT" in diags[0].message


def test_flags_count_distinct_lists_both():
    diags = _check('q = "SELECT COUNT(DISTINCT org_id) FROM call"\n')
    assert len(diags) == 1
    assert "COUNT(" in diags[0].message
    assert "DISTINCT" in diags[0].message


def test_flags_multiline_concatenated_query():
    src = 'q = (\n  "SELECT user_id, COUNT(*) "\n  "FROM call GROUP BY user_id"\n)\n'
    assert len(_check(src)) == 1


def test_allows_point_read():
    assert _check('q = "SELECT id, status FROM call WHERE id = %s"\n') == []


def test_ignores_non_query_string():
    # No FROM → not a query (e.g. a count-related identifier or message).
    assert _check('msg = "distinct count of group members"\n') == []


def test_ignores_count_column_without_from():
    assert _check('label = "GROUP BY clause"\n') == []


def test_respects_noqa():
    src = 'q = "SELECT COUNT(*) FROM call"  # sarj-noqa: SARJ020\n'
    rule = NoAggregationInStoreQuery()

    diags = rule.check(Path("call_store.py"), src)
    lines = src.splitlines()
    kept = [d for d in diags if not is_suppressed(lines, d.line, d.code)]
    assert kept == []


def test_strips_sql_comment_false_positive():
    # COUNT mentioned only in a SQL comment is not a real aggregation.
    src = 'q = "SELECT id FROM call -- COUNT here is just prose\\n WHERE id = %s"\n'
    assert _check(src) == []


def test_ignores_clickhouse_store_file():
    # A ClickHouse store (the columnar mirror) is exactly where aggregation belongs.
    src = 'from clickhouse_connect.driver import AsyncClient\nq = "SELECT status, COUNT(*) FROM call GROUP BY status"\n'
    assert _check(src) == []


def test_ignores_clickhouse_flavored_query():
    src = 'q = "SELECT argMax(status, _peerdb_version), COUNT(*) FROM call GROUP BY org"\n'
    assert _check(src) == []


def test_handles_syntax_error():
    assert _check("def (:\n") == []
