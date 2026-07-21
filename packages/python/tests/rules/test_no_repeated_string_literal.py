from pathlib import Path
from typing import TYPE_CHECKING

from sarj_python_lint.rules.no_repeated_string_literal import NoRepeatedStringLiteral


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic

_LONG_SQL = "\n                SELECT id, name, created_at FROM organization\n            "
assert len(_LONG_SQL) >= 40


def _check(source: str, filename: str = "module.py") -> list[Diagnostic]:
    return NoRepeatedStringLiteral().check(Path(filename), source)


def test_flags_structured_sql_repeated_across_functions():
    src = f'''
def insert():
    return """{_LONG_SQL}"""

def fetch():
    return """{_LONG_SQL}"""
'''
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ024"
    assert "first use at line 3" in diags[0].message


def test_flags_each_repeat_beyond_the_first():
    src = f'''
A = 0
def a():
    return """{_LONG_SQL}"""
def b():
    return """{_LONG_SQL}"""
def c():
    return """{_LONG_SQL}"""
'''
    diags = _check(src)
    assert len(diags) == 2


def test_flags_constraint_name_across_methods():
    constraint = "custom_scenario_organization_id_name_key"
    assert len(constraint) >= 40
    src = f"""
class Store:
    def upsert(self):
        return "{constraint}"
    def update(self):
        return "{constraint}"
"""
    assert len(_check(src)) == 1


def test_allows_single_occurrence():
    src = f'def x():\n    return """{_LONG_SQL}"""\n'
    assert _check(src) == []


def test_allows_repeated_short_literal():
    src = """
def a():
    return "utf-8"
def b():
    return "utf-8"
"""
    assert _check(src) == []


def test_ignores_unstructured_prose_across_functions():
    msg = "Phone number must contain only digits and an optional leading plus sign"
    assert len(msg) >= 40
    src = f"""
def a():
    raise ValueError("{msg}")
def b():
    raise ValueError("{msg}")
"""
    assert _check(src) == []


def test_ignores_coincidental_error_message_pair_same_function():
    """The JSON_PARSE_ERROR / VALIDATION_FAILED coincidental-coupling regression."""
    shared = "The AI generated an invalid response format. Please try again."
    src = f"""
def get_user_error_message(code):
    return {{
        "JSON_PARSE_ERROR": "{shared}",
        "VALIDATION_FAILED": "{shared}",
    }}[code]
"""
    assert _check(src) == []


def test_ignores_lowercase_from_in_prose():
    """SQL keyword match is case-sensitive so prose containing 'from' is not structural."""
    prose = "Extract success criteria from the system prompt and evaluate them"
    assert len(prose) >= 40
    src = f"""
def a():
    return "{prose}"
def b():
    return "{prose}"
"""
    assert _check(src) == []


def test_ignores_same_function_duplicate():
    src = f'''
def only_here():
    first = """{_LONG_SQL}"""
    second = """{_LONG_SQL}"""
    return first, second
'''
    assert _check(src) == []


def test_ignores_module_level_only_duplicate():
    src = f'''
A = """{_LONG_SQL}"""
B = """{_LONG_SQL}"""
'''
    assert _check(src) == []


def test_allows_repeated_fstring_fragments():
    src = """
def a(x):
    return f"SELECT * FROM task WHERE organization_id = {x} AND status = 'x'"

def b(x):
    return f"SELECT * FROM task WHERE organization_id = {x} AND status = 'x'"
"""
    assert _check(src) == []


def test_flags_repeated_format_template_across_functions():
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


def test_excludes_field_description_scaffolding():
    desc = "Tool identifier. Valid values: transfer-to-human, end-call, custom-api"
    src = f"""
class A(BaseModel):
    slug: str = Field(description="{desc}")

class B(BaseModel):
    slug: str = Field(description="{desc}")
"""
    assert _check(src) == []


def test_excludes_field_examples_scaffolding():
    src = f"""
class A(BaseModel):
    id: str = Field(examples=["{_LONG_SQL}"])

class B(BaseModel):
    id: str = Field(examples=["{_LONG_SQL}"])
"""
    assert _check(src) == []


def test_excludes_title_and_summary_scaffolding():
    text = "SELECT id FROM organization ORDER BY created_at DESC"
    src = f"""
class A(BaseModel):
    a: str = Field(title="{text}")
    b: str = Field(summary="{text}")
"""
    assert _check(src) == []


def test_skips_test_files_and_conftest():
    src = f'''
def a():
    return """{_LONG_SQL}"""
def b():
    return """{_LONG_SQL}"""
'''
    assert _check(src, filename="test_module.py") == []
    assert _check(src, filename="conftest.py") == []
    assert _check(src, filename="tests/factories.py") == []


def test_syntax_error_returns_no_diagnostics():
    assert _check("def broken(:\n") == []


def test_message_previews_are_truncated():
    long_value = "SELECT " + "x" * 120
    src = f"""
def a():
    return "{long_value}"
def b():
    return "{long_value}"
"""
    diags = _check(src)
    assert len(diags) == 1
    assert "x" * 41 not in diags[0].message
