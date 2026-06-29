"""SARJ201: stateful Terraform resources must keep `deletion_protection = true`.

A `terraform apply` (or `destroy`) that drops a database, cluster, or warehouse
is unrecoverable. Cloud providers expose a `deletion_protection` flag exactly to
make that mistake impossible without an explicit two-step removal; leaving it off
(or `= false`) means a stray plan can delete production data.

    # flagged — no deletion_protection
    resource "google_sql_database_instance" "main" {
      name = "prod"
    }

    # flagged — explicitly disabled
    resource "google_sql_database_instance" "main" {
      deletion_protection = false
    }

    # ok
    resource "google_sql_database_instance" "main" {
      deletion_protection = true
    }

Only resources that actually expose a `deletion_protection` argument are checked.
Suppress a deliberate ephemeral resource with `# sarj-noqa: SARJ201 — <reason>`
on the `resource` line.
"""

from __future__ import annotations

import re
from pathlib import Path

from sarj_iac_lint.rule_base import Diagnostic, Rule

_PROTECTED_TYPES = frozenset(
    {
        "google_sql_database_instance",
        "google_container_cluster",
        "google_bigquery_table",
        "google_spanner_database",
        "google_alloydb_cluster",
        "aws_db_instance",
        "aws_rds_cluster",
        "aws_redshift_cluster",
    }
)

_RESOURCE_RE = re.compile(r'^\s*resource\s+"([a-z0-9_]+)"\s+"([^"]+)"\s*\{')
_DELPROT_RE = re.compile(r"^\s*deletion_protection(?:_enabled)?\s*=\s*(\S+)")
_PREVENT_DESTROY_RE = re.compile(r"^\s*prevent_destroy\s*=\s*true\b")


class RequireDeletionProtection(Rule):
    """Stateful resource without deletion_protection = true."""

    id = "require-deletion-protection"
    code = "SARJ201"
    description = (
        "Stateful resource (Cloud SQL, GKE, BigQuery, RDS, ...) must set "
        "deletion_protection = true so a stray apply cannot destroy prod data."
    )

    def check(self, path: Path, source: str) -> list[Diagnostic]:
        if not str(path).endswith((".tf", ".tf.json", ".hcl")):
            return []
        lines = source.splitlines()
        diags: list[Diagnostic] = []
        i = 0
        n = len(lines)
        while i < n:
            m = _RESOURCE_RE.match(lines[i])
            if m is None or m.group(1) not in _PROTECTED_TYPES:
                i += 1
                continue
            rtype, rname = m.group(1), m.group(2)
            start = i
            end = _block_end(lines, i)
            state = _protection_state(lines[start : end + 1])
            if state != "protected":
                detail = (
                    "deletion_protection = false"
                    if state == "disabled"
                    else "no deletion_protection / prevent_destroy"
                )
                diags.append(
                    Diagnostic(
                        path=path,
                        line=start + 1,
                        col=lines[start].index("resource") + 1,
                        code=self.code,
                        message=(
                            f'resource "{rtype}" "{rname}" has {detail} — keep '
                            "deletion_protection = true (or lifecycle.prevent_destroy) "
                            "so a stray apply/destroy cannot wipe prod data."
                        ),
                    )
                )
            i = end + 1
        return diags


def _block_end(lines: list[str], start: int) -> int:
    """Index of the line closing the block opened on `start` (brace-balanced)."""
    depth = 0
    for j in range(start, len(lines)):
        depth += lines[j].count("{") - lines[j].count("}")
        if depth <= 0 and j > start:
            return j
        if depth <= 0 and j == start and "}" in lines[j]:
            return j
    return len(lines) - 1


def _protection_state(block: list[str]) -> str:
    """'protected' / 'disabled' / 'missing' for the block.

    Any `deletion_protection = <value>` counts as protected unless it is a
    literal `false` (var/expression-gated protection is an intentional per-env
    pattern, not a violation). `lifecycle { prevent_destroy = true }` also
    protects.
    """
    for line in block:
        m = _DELPROT_RE.match(line)
        if m is not None:
            return "disabled" if m.group(1).rstrip(",") == "false" else "protected"
    for line in block:
        if _PREVENT_DESTROY_RE.match(line):
            return "protected"
    return "missing"
