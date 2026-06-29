from pathlib import Path

from sarj_iac_lint.rules.no_hardcoded_cloud_resource_id import (
    NoHardcodedCloudResourceId,
)


def _check(source: str, name: str = "main.tf") -> list:
    return NoHardcodedCloudResourceId().check(Path(name), source)


def test_flags_hardcoded_project_id():
    diags = _check('  project = "sarj-bulbul"\n')
    assert len(diags) == 1
    assert "sarj-bulbul" in diags[0].message


def test_flags_project_id_attr_variant():
    assert len(_check('  project_id = "my-prod-123"\n')) == 1


def test_allows_var_project():
    assert _check("  project = var.project\n") == []


def test_allows_variable_default_block():
    # Declaring the project variable's default is fine — it's `default =`, not `project =`.
    src = 'variable "project" {\n  default = "sarj-bulbul"\n}\n'
    assert _check(src) == []


def test_ignores_tfvars_file():
    # tfvars is the correct home for an env-specific literal project id.
    assert _check('project = "sarj-bulbul"\n', name="prod.tfvars") == []


def test_ignores_region_literals():
    assert _check('  region = "me-central2"\n') == []


def test_ignores_non_hyphenated_value():
    assert _check('  project = "default"\n') == []


def test_ignores_comment():
    assert _check('  # project = "sarj-bulbul"\n') == []


def test_ignores_non_tf_file():
    assert _check('project = "sarj-bulbul"\n', name="notes.md") == []
