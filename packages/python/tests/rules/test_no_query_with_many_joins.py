from pathlib import Path

from sarj_python_lint.rule_base import is_suppressed
from sarj_python_lint.rules.no_query_with_many_joins import NoQueryWithManyJoins


def _check(source: str) -> list:
    return NoQueryWithManyJoins().check(Path("foo_store.py"), source)


def test_flags_three_joins():
    src = '''q = """
SELECT *
FROM call c
JOIN user u ON u.id = c.user_id
JOIN organization o ON o.id = c.org_id
JOIN scenario s ON s.id = c.scenario_id
"""'''
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ019"
    assert "3 JOINs" in diags[0].message


def test_allows_two_joins():
    src = '''q = """
SELECT *
FROM call c
JOIN user u ON u.id = c.user_id
LEFT JOIN organization o ON o.id = c.org_id
"""'''
    assert _check(src) == []


def test_allows_single_join():
    src = 'q = "SELECT * FROM a JOIN b ON a.id = b.a_id"'
    assert _check(src) == []


def test_allows_no_join():
    src = 'q = "SELECT id FROM task WHERE id = %s"'
    assert _check(src) == []


def test_counts_qualified_join_variants_each_once():
    src = '''q = """
SELECT *
FROM a
LEFT JOIN b ON TRUE
RIGHT JOIN c ON TRUE
INNER JOIN d ON TRUE
FULL JOIN e ON TRUE
"""'''
    diags = _check(src)
    assert len(diags) == 1
    assert "4 JOINs" in diags[0].message


def test_ignores_join_in_sql_comment():
    src = '''q = """
SELECT *
FROM a
JOIN b ON TRUE
JOIN c ON TRUE
-- JOIN d ON TRUE  (removed)
"""'''
    assert _check(src) == []


def test_ignores_join_in_block_comment():
    src = '''q = """
SELECT * FROM a
JOIN b ON TRUE
JOIN c ON TRUE
/* JOIN d ON TRUE */
"""'''
    assert _check(src) == []


def test_requires_from_to_consider_string():
    src = 'msg = "please JOIN the call. JOIN now. JOIN us."'
    assert _check(src) == []


def test_case_insensitive():
    src = '''q = """
select * from a
join b on true
join c on true
join d on true
"""'''
    assert len(_check(src)) == 1


def test_concatenated_query_counts_across_parts():
    src = """q = (
    "SELECT * FROM a "
    "JOIN b ON TRUE "
    "JOIN c ON TRUE "
    "JOIN d ON TRUE"
)"""
    assert len(_check(src)) == 1


def test_suppressed_by_sarj_noqa():

    src = (
        'q = "SELECT * FROM a JOIN b ON TRUE JOIN c ON TRUE JOIN d ON TRUE"  '
        "# sarj-noqa: SARJ019 — reporting view, intentional"
    )
    diags = _check(src)
    assert len(diags) == 1
    assert is_suppressed(src.splitlines(), diags[0].line, diags[0].code)


def test_syntax_error_returns_empty():
    assert _check("def (:::") == []
