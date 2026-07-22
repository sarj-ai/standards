from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from sarj_python_lint.rules.json_response_not_parsed import JsonResponseNotParsed


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic


def _check(source: str) -> list[Diagnostic]:
    return JsonResponseNotParsed().check(Path("<test>.py"), source)


# --- fires: external JSON payload consumed untyped ---


def test_flags_json_call_subscript():
    diags = _check('token = resp.json()["access_token"]\n')
    assert len(diags) == 1
    assert diags[0].code == "SARJ030"


def test_flags_json_call_get():
    assert len(_check('data = resp.json().get("data")\n')) == 1


def test_flags_awaited_client_json_subscript():
    assert len(_check('v = (await client.get(u)).json()["k"]\n')) == 1


def test_flags_json_loads_subscript():
    assert len(_check('v = json.loads(body)["k"]\n')) == 1


def test_flags_json_loads_get():
    assert len(_check('v = json.loads(body).get("k")\n')) == 1


def test_flags_json_load_subscript():
    assert len(_check('v = json.load(fh)["k"]\n')) == 1


def test_flags_json_call_attribute():
    assert len(_check("v = resp.json().field\n")) == 1


def test_flags_chained_subscript_reports_inner_once():
    # `resp.json()["data"]["id"]` — only the inner access chains directly off the
    # json call; the outer subscript reads a subscript, not the json call.
    diags = _check('v = resp.json()["data"]["id"]\n')
    assert len(diags) == 1


# --- must not fire ---


def test_ignores_assign_then_subscript():
    src = """
d = resp.json()
v = d["k"]
"""
    assert _check(src) == []


def test_ignores_json_call_with_args():
    assert _check('v = resp.json(cls=X)["k"]\n') == []


def test_ignores_json_call_with_positional_args():
    assert _check('v = resp.json(object_hook=h)["k"]\n') == []


def test_ignores_payload_passed_to_parser():
    assert _check("m = Model.model_validate(resp.json())\n") == []


def test_ignores_plain_dict_literal_subscript():
    assert _check('v = {"a": 1}["a"]\n') == []


def test_ignores_non_call_json_attribute():
    assert _check("v = obj.json\n") == []


def test_ignores_bare_json_call_not_chained():
    assert _check("v = resp.json()\n") == []


def test_ignores_json_dumps():
    assert _check("s = json.dumps(x)\n") == []


def test_ignores_non_json_module_loads():
    # `yaml.loads(...)` is not the JSON payload accessor.
    assert _check('v = yaml.loads(body)["k"]\n') == []


# --- edge cases ---


def test_empty_source():
    assert _check("") == []


def test_syntax_error_returns_empty():
    assert _check("def f(:\n") == []


# --- line/col + sorting ---


def test_line_and_col_subscript():
    diags = _check('x = resp.json()["k"]\n')
    assert len(diags) == 1
    assert diags[0].line == 1
    assert diags[0].col == 5


def test_line_and_col_get():
    diags = _check('x = resp.json().get("k")\n')
    assert len(diags) == 1
    assert diags[0].line == 1
    assert diags[0].col == 5


def test_multiple_hits_sorted():
    src = """
a = resp.json()["one"]
b = other.json().get("two")
"""
    diags = _check(src)
    assert len(diags) == 2
    assert [(d.line, d.col) for d in diags] == [(2, 5), (3, 5)]


@pytest.mark.parametrize(
    "expr",
    [
        'resp.json()["k"]',
        'resp.json().get("k")',
        "resp.json().field",
        'json.loads(body)["k"]',
        'json.loads(body).get("k")',
    ],
)
def test_parametrized_fires(expr: str):
    assert len(_check(f"v = {expr}\n")) == 1


@pytest.mark.parametrize(
    "expr",
    [
        'resp.json(cls=X)["k"]',
        "Model.model_validate(resp.json())",
        '{"a": 1}["a"]',
        "obj.json",
        "json.dumps(x)",
    ],
)
def test_parametrized_does_not_fire(expr: str):
    assert _check(f"v = {expr}\n") == []
