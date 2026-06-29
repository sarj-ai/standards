from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sarj_iac_lint.rules.require_deletion_protection import RequireDeletionProtection


if TYPE_CHECKING:
    from sarj_iac_lint.rule_base import Diagnostic


def _check(source: str, name: str = "main.tf") -> list[Diagnostic]:
    return RequireDeletionProtection().check(Path(name), source)


def test_flags_missing_deletion_protection():
    src = """
resource "google_sql_database_instance" "main" {
  name = "prod"
}
"""
    diags = _check(src)
    assert len(diags) == 1
    assert "no deletion_protection" in diags[0].message


def test_allows_variable_gated_protection():
    src = """
resource "google_sql_database_instance" "logto" {
  deletion_protection = var.gke_deletion_protection
}
"""
    assert _check(src) == []


def test_allows_prevent_destroy_lifecycle():
    src = """
resource "google_container_cluster" "data" {
  name = "data"
  lifecycle {
    prevent_destroy = true
  }
}
"""
    assert _check(src) == []


def test_flags_explicitly_disabled():
    src = """
resource "google_container_cluster" "primary" {
  deletion_protection = false
}
"""
    diags = _check(src)
    assert len(diags) == 1
    assert "false" in diags[0].message


def test_allows_protection_enabled():
    src = """
resource "google_sql_database_instance" "main" {
  name                = "prod"
  deletion_protection = true
}
"""
    assert _check(src) == []


def test_ignores_unprotected_resource_types():
    src = """
resource "google_storage_bucket_object" "x" {
  name = "y"
}
"""
    assert _check(src) == []


def test_handles_nested_blocks():
    src = """
resource "google_container_cluster" "primary" {
  node_config {
    machine_type = "e2-medium"
  }
  deletion_protection = true
}
"""
    assert _check(src) == []


def test_flags_each_unprotected_instance():
    src = """
resource "aws_db_instance" "a" {
  engine = "postgres"
}
resource "aws_db_instance" "b" {
  deletion_protection = true
}
"""
    assert len(_check(src)) == 1


def test_ignores_non_tf_files():
    src = 'resource "google_sql_database_instance" "main" {\n}\n'
    assert _check(src, name="notes.txt") == []


def test_brace_in_string_does_not_truncate_block():
    # A `}` inside a string must not end the block early and produce a phantom
    # "no deletion_protection" FP — the protected value comes after it.
    src = """
resource "google_sql_database_instance" "main" {
  description         = "closes with }"
  deletion_protection = true
}
"""
    assert _check(src) == []


def test_quoted_false_is_disabled():
    src = """
resource "google_sql_database_instance" "main" {
  deletion_protection = "false"
}
"""
    diags = _check(src)
    assert len(diags) == 1
    assert "false" in diags[0].message


def test_quoted_true_is_protected():
    src = """
resource "google_sql_database_instance" "main" {
  deletion_protection = "true"
}
"""
    assert _check(src) == []


def test_heredoc_brace_does_not_truncate_block():
    src = """
resource "google_sql_database_instance" "main" {
  user_labels = jsonencode({})
  startup     = <<-EOT
    if true; then echo "}"; fi
  EOT
  deletion_protection = true
}
"""
    assert _check(src) == []


def test_flags_newly_allowlisted_dynamodb():
    src = """
resource "aws_dynamodb_table" "sessions" {
  name = "sessions"
}
"""
    assert len(_check(src)) == 1


def test_flags_newly_allowlisted_azurerm_server():
    src = """
resource "azurerm_postgresql_flexible_server" "db" {
  name = "db"
}
"""
    assert len(_check(src)) == 1
