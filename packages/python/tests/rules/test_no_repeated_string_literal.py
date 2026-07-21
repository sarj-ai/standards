from pathlib import Path
from typing import TYPE_CHECKING

from sarj_python_lint.rules.no_repeated_string_literal import NoRepeatedStringLiteral


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic

_LONG = "SELECT id, name, created_at, updated_at FROM organization"
assert len(_LONG) >= 40


def _check(source: str, filename: str = "module.py") -> list[Diagnostic]:
    return NoRepeatedStringLiteral().check(Path(filename), source)


def test_flags_second_occurrence_of_long_literal():
    src = f"""
def insert():
    return "{_LONG}"

def fetch():
    return "{_LONG}"
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ024"
    assert diags[0].line == 6
    assert "first use at line 3" in diags[0].message


def test_flags_each_repeat_beyond_the_first():
    src = f"""
A = "{_LONG}"
B = "{_LONG}"
C = "{_LONG}"
"""
    diags = _check(src)
    assert [d.line for d in diags] == [3, 4]


def test_allows_single_occurrence():
    src = f'X = "{_LONG}"\n'
    assert _check(src) == []


def test_allows_repeated_short_literal():
    src = """
A = "utf-8"
B = "utf-8"
C = "utf-8"
"""
    assert _check(src) == []


def test_allows_repeated_fstring_fragments():
    src = """
def a(x):
    return f"a very long shared fragment of an f-string here {x} end"

def b(x):
    return f"a very long shared fragment of an f-string here {x} end"
"""
    assert _check(src) == []


def test_flags_repeated_format_template():
    template = "SELECT {fields} FROM task WHERE organization_id = %(org)s"
    src = f"""
def get():
    return "{template}".format(fields="id")

def list_all():
    return "{template}".format(fields="id, status")
"""
    assert len(_check(src)) == 1


def test_allows_repeated_docstring():
    doc = "This docstring is deliberately identical across both functions here."
    src = f'''
def a():
    """{doc}"""

def b():
    """{doc}"""
'''
    assert _check(src) == []


def test_flags_repeat_inside_dict_values():
    src = f"""
MESSAGES = {{
    "en": "{_LONG}",
    "ar": "{_LONG}",
}}
"""
    assert len(_check(src)) == 1


def test_allows_repeated_field_examples():
    src = f"""
class A(BaseModel):
    id: str = Field(examples=["{_LONG}"])

class B(BaseModel):
    id: str = Field(examples=["{_LONG}"])
"""
    assert _check(src) == []


def test_skips_test_files_and_conftest():
    src = f"""
A = "{_LONG}"
B = "{_LONG}"
"""
    assert _check(src, filename="test_module.py") == []
    assert _check(src, filename="conftest.py") == []
    assert _check(src, filename="tests/factories.py") == []


def test_syntax_error_returns_no_diagnostics():
    assert _check("def broken(:\n") == []


def test_message_previews_are_truncated():
    long_value = "x" * 120
    src = f"""
A = "{long_value}"
B = "{long_value}"
"""
    diags = _check(src)
    assert len(diags) == 1
    assert "x" * 41 not in diags[0].message
