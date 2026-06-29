from pathlib import Path

from sarj_python_lint.rule_base import is_suppressed
from sarj_python_lint.rules.no_select_star import NoSelectStar


def _check(source: str) -> list:
    return NoSelectStar().check(Path("call_store.py"), source)


def test_flags_select_star():
    diags = _check('q = "SELECT * FROM call WHERE id = %s"\n')
    assert len(diags) == 1
    assert "SELECT *" in diags[0].message


def test_flags_qualified_star():
    assert len(_check('q = "SELECT c.* FROM call c"\n')) == 1


def test_flags_star_with_other_columns():
    assert len(_check('q = "SELECT *, extra FROM call"\n')) == 1


def test_flags_multiline_concatenated():
    src = 'q = (\n  "SELECT * "\n  "FROM call WHERE id = %s"\n)\n'
    assert len(_check(src)) == 1


def test_allows_explicit_columns():
    assert _check('q = "SELECT id, status FROM call WHERE id = %s"\n') == []


def test_allows_count_star():
    assert _check('q = "SELECT COUNT(*) FROM call"\n') == []


def test_allows_exists_select_star():
    src = 'q = "SELECT id FROM call c WHERE EXISTS (SELECT * FROM batch b WHERE b.id = c.batch_id)"\n'
    assert _check(src) == []


def test_ignores_non_query_string():
    assert _check('msg = "select * everything you want"\n') == []


def test_respects_noqa():

    src = 'q = "SELECT * FROM call"  # sarj-noqa: SARJ021\n'
    diags = NoSelectStar().check(Path("call_store.py"), src)
    kept = [d for d in diags if not is_suppressed(src.splitlines(), d.line, d.code)]
    assert kept == []


def test_handles_syntax_error():
    assert _check("def (:\n") == []
