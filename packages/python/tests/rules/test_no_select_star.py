from pathlib import Path

import pytest

from sarj_python_lint.rule_base import is_suppressed
from sarj_python_lint.rules.no_select_star import NoSelectStar


def _check(source: str, path: str = "call_store.py") -> list:
    return NoSelectStar().check(Path(path), source)


def _kept(source: str, path: str = "call_store.py") -> list:
    diags = _check(source, path)
    lines = source.splitlines()
    return [d for d in diags if not is_suppressed(lines, d.line, d.code)]


FIRES = {
    "basic": 'q = "SELECT * FROM call WHERE id = %s"\n',
    "qualified_alias": 'q = "SELECT c.* FROM call c"\n',
    "star_with_other_cols": 'q = "SELECT *, extra FROM call"\n',
    "distinct_star": 'q = "SELECT DISTINCT * FROM call"\n',
    "all_star": 'q = "SELECT ALL * FROM call"\n',
    "lowercase": 'q = "select * from call"\n',
    "mixed_case": 'q = "SeLeCt * FrOm call"\n',
    "tab_between": 'q = "SELECT\t* FROM call"\n',
    "triple_quoted_newlines": 'q = """SELECT\n*\nFROM call"""\n',
    "escaped_newline": 'q = "SELECT *\\nFROM call"\n',
    "subquery_star": 'q = "SELECT id FROM (SELECT * FROM call) t"\n',
    "with_cte_then_star": 'q = "WITH x AS (SELECT id FROM a) SELECT * FROM x"\n',
    "insert_select_star": 'q = "INSERT INTO b SELECT * FROM a"\n',
    "union_of_stars": 'q = "SELECT * FROM a UNION SELECT * FROM b"\n',
    "star_before_from_alias": 'q = "SELECT call.* FROM call"\n',
    "fstring_static_prefix": 'q = f"SELECT * FROM call WHERE id = {x}"\n',
    "fstring_from_after_interp": 'q = f"SELECT * FROM {t}"\n',
    "star_then_name_concat": 'q = "SELECT * FROM " + tbl\n',
    "newline_after_select": 'q = "SELECT\\n  * FROM call"\n',
}


@pytest.mark.parametrize("source", FIRES.values(), ids=list(FIRES))
def test_fires_one_diagnostic(source: str):
    assert len(_check(source)) == 1


ALLOWS = {
    "explicit_columns": 'q = "SELECT id, status FROM call WHERE id = %s"\n',
    "count_star": 'q = "SELECT COUNT(*) FROM call"\n',
    "count_distinct": 'q = "SELECT COUNT(DISTINCT org_id) FROM call"\n',
    "exists_select_star": 'q = "SELECT id FROM call c WHERE EXISTS (SELECT * FROM b WHERE b.id = c.b_id)"\n',
    "not_exists_select_star": 'q = "SELECT id FROM a WHERE NOT EXISTS (SELECT * FROM b)"\n',
    "exists_lowercase": 'q = "select id from a where exists (select * from b)"\n',
    "prose_star_no_from": 'msg = "select * everything you want"\n',
    "star_without_from": 'q = "SELECT * , 1"\n',
    "bytes_literal": 'q = b"SELECT * FROM call"\n',
    "block_comment_only": 'q = "/* SELECT * FROM call */ SELECT id FROM call"\n',
    "line_comment_only": 'q = "SELECT id FROM call -- SELECT * FROM x"\n',
    "empty_string": 'q = ""\n',
    "unicode_columns": 'q = "SELECT naïve, café FROM call"\n',
    "prose_no_query_shape": 'msg = "This report is distinct from the last one."\n',
    "identifier_named_from": 'label = "star rating"\n',
}


@pytest.mark.parametrize("source", ALLOWS.values(), ids=list(ALLOWS))
def test_does_not_fire(source: str):
    assert _check(source) == []


@pytest.mark.parametrize(
    "source",
    [
        'q = (\n  "SELECT * "\n  "FROM call WHERE id = %s"\n)\n',
        'q = "SELECT * " + "FROM call WHERE id = %s"\n',
        'q = "SELECT * " "FROM call"\n',
    ],
    ids=["implicit_adjacent_multiline", "explicit_plus_concat", "implicit_adjacent_inline"],
)
def test_flags_concatenated_queries(source: str):
    assert len(_check(source)) == 1


def test_message_and_code_fields():
    diags = _check('q = "SELECT * FROM call"\n')
    assert len(diags) == 1
    assert diags[0].code == "SARJ021"
    assert "SELECT *" in diags[0].message
    assert "class_row" in diags[0].message
    assert "sarj-noqa: SARJ021" in diags[0].message


def test_line_and_col_single():
    diags = _check('x = 1\nq = "SELECT * FROM call"\n')
    assert len(diags) == 1
    assert diags[0].line == 2
    assert diags[0].col == 5


def test_line_and_col_of_qualified_star():
    diags = _check('\n\nquery = "SELECT c.* FROM call c"\n')
    assert len(diags) == 1
    assert diags[0].line == 3
    assert diags[0].col == 9


def test_two_violations_sorted_by_line():
    diags = _check('a = "SELECT * FROM call"\nb = "SELECT c.* FROM call c"\n')
    assert [(d.line, d.col) for d in diags] == [(1, 5), (2, 5)]


def test_two_violations_same_line_sorted_by_col():
    diags = _check('t = ("SELECT * FROM a", "SELECT * FROM b")\n')
    assert [(d.line, d.col) for d in diags] == [(1, 6), (1, 25)]


def test_reports_all_violations_in_file():
    src = (
        'a = "SELECT * FROM call"\n'
        'b = "SELECT id FROM call"\n'
        'c = "SELECT x.* FROM call x"\n'
        'd = "SELECT COUNT(*) FROM call"\n'
    )
    diags = _check(src)
    assert [d.line for d in diags] == [1, 3]


def test_outer_star_fires_while_inner_exists_exempt():
    src = 'q = "SELECT * FROM a WHERE EXISTS (SELECT * FROM b)"\n'
    diags = _check(src)
    assert len(diags) == 1


def test_earlier_exists_does_not_exempt_later_in_subquery_star():
    src = 'q = "SELECT id FROM a WHERE EXISTS (SELECT 1 FROM b) OR x IN (SELECT * FROM d)"\n'
    assert len(_check(src)) == 1


def test_fires_regardless_of_filename():
    assert len(_check('q = "SELECT * FROM call"\n', path="service.py")) == 1


@pytest.mark.parametrize(
    "source",
    [
        'q = "SELECT * FROM call"  # sarj-noqa\n',
        'q = "SELECT * FROM call"  # sarj-noqa: SARJ021\n',
        'q = "SELECT * FROM call"  # sarj-noqa: SARJ020, SARJ021\n',
    ],
    ids=["bare", "exact_code", "multi_code"],
)
def test_respects_noqa(source: str):
    assert _kept(source) == []


def test_wrong_noqa_code_not_suppressed():
    src = 'q = "SELECT * FROM call"  # sarj-noqa: SARJ020\n'
    assert len(_kept(src)) == 1


@pytest.mark.parametrize(
    "source",
    ["", "   \n\t\n", "# only a comment\n", "x = 1 + 2\n", 'name = "no sql here"\n'],
    ids=["empty", "whitespace", "comment_only", "no_strings", "plain_string"],
)
def test_boundary_inputs_return_empty(source: str):
    assert _check(source) == []


@pytest.mark.parametrize(
    "source",
    ["def (:\n", "q = 'SELECT * FROM call\n", "class A(:\n    pass\n"],
    ids=["bad_def", "unterminated_string", "bad_class"],
)
def test_syntax_error_returns_empty(source: str):
    assert _check(source) == []


@pytest.mark.xfail(
    reason="FN: multi-part qualified star like `public.call.*` is not matched by "
    "_SELECT_STAR (only a single `<alias>.` prefix is allowed before `*`).",
    strict=True,
)
def test_schema_qualified_star_should_fire():
    assert len(_check('q = "SELECT public.call.* FROM call"\n')) == 1
