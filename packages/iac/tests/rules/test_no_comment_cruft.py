from pathlib import Path

from sarj_iac_lint.rules.no_comment_cruft import NoCommentCruft


def _check(source: str, name: str = "main.tf") -> list:
    return NoCommentCruft().check(Path(name), source)


def test_flags_commented_out_resource():
    src = """
# resource "google_storage_bucket" "old" {
resource "google_storage_bucket" "new" {}
"""
    diags = _check(src)
    assert len(diags) == 1
    assert "Commented-out" in diags[0].message


def test_flags_commented_out_attribute():
    src = 'name = "x"\n# ttl = 3600\n'
    assert len(_check(src)) == 1


def test_flags_section_banner():
    src = "# ============================================\nlocals {}\n"
    assert len(_check(src)) == 1


def test_flags_double_slash_comment_code():
    src = '// module "vpc" {\nmodule "vpc2" {}\n'
    assert len(_check(src)) == 1


def test_allows_prose_why_comment():
    src = '# keep this bucket in us-central1 for data residency\nresource "x" "y" {}\n'
    assert _check(src) == []


def test_allows_directive_comments():
    src = """
# tflint-ignore: terraform_unused_declarations
# checkov:skip=CKV_GCP_1: justified
# sarj-noqa: SARJ201 — ephemeral
# TODO: split this module
variable "x" {}
"""
    assert _check(src) == []


def test_yaml_only_flags_banners_not_keys():
    # In YAML, `key: value` prose must NOT be treated as commented-out code.
    src = "# note: remember to bump the chart version\n# ------------------------------\nname: app\n"
    diags = _check(src, name="values.yaml")
    assert len(diags) == 1
    assert "banner" in diags[0].message.lower()


def test_allows_short_equals_in_prose():
    src = "# use == for comparison in the policy\nx = 1\n"
    assert _check(src) == []


def test_tfvars_commented_inputs_not_flagged_only_banners():
    # Commented `key = ""` menus in .tfvars are conventional, not dead code.
    src = '# twilio_account_sid = ""\n# =========================\nstack = "prod"\n'
    diags = _check(src, name="prod.tfvars")
    assert len(diags) == 1
    assert "banner" in diags[0].message.lower()
