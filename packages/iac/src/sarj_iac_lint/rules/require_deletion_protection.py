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
from typing import TYPE_CHECKING, final, override

from sarj_iac_lint._hcl import heredoc_body_mask, mask_line, strip_inline_comment
from sarj_iac_lint.rule_base import Diagnostic, Rule


if TYPE_CHECKING:
    from pathlib import Path

# Curated set of stateful resources whose accidental destroy is unrecoverable.
# Each either exposes a `deletion_protection[_enabled]` argument or is a data
# store that should at minimum carry `lifecycle { prevent_destroy = true }`.
_PROTECTED_TYPES = frozenset(
    {
        # GCP
        "google_sql_database_instance",
        "google_container_cluster",
        "google_bigquery_table",
        "google_bigquery_dataset",
        "google_spanner_database",
        "google_alloydb_cluster",
        "google_bigtable_instance",
        "google_redis_instance",
        # AWS
        "aws_db_instance",
        "aws_rds_cluster",
        "aws_rds_global_cluster",
        "aws_redshift_cluster",
        "aws_dynamodb_table",
        "aws_elasticache_replication_group",
        "aws_elasticache_cluster",
        "aws_docdb_cluster",
        "aws_neptune_cluster",
        # Azure
        "azurerm_postgresql_flexible_server",
        "azurerm_postgresql_server",
        "azurerm_mysql_flexible_server",
        "azurerm_mysql_server",
        "azurerm_mssql_server",
        "azurerm_mssql_database",
        "azurerm_cosmosdb_account",
    }
)

_RESOURCE_RE = re.compile(r'^\s*resource\s+"([a-z0-9_]+)"\s+"([^"]+)"\s*\{')
_DELPROT_RE = re.compile(r"^\s*deletion_protection(?:_enabled)?\s*=\s*(\S+)")
_PREVENT_DESTROY_RE = re.compile(r"^\s*prevent_destroy\s*=\s*true\b")


@final
class RequireDeletionProtection(Rule):
    """Stateful resource without deletion_protection = true."""

    id = "require-deletion-protection"
    code = "SARJ201"
    description = (
        "Stateful resource (Cloud SQL, GKE, BigQuery, RDS, ...) must set "
        "deletion_protection = true so a stray apply cannot destroy prod data."
    )

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        if not str(path).endswith((".tf", ".tf.json", ".hcl")):
            return []
        lines = source.splitlines()
        hmask = heredoc_body_mask(lines)
        # `masked` blanks string contents (for brace balancing); `logical`
        # keeps string contents but drops comments (for keyword/value matching).
        # Heredoc body lines collapse to "" in both — they are data, not HCL.
        masked = ["" if h else mask_line(ln) for ln, h in zip(lines, hmask, strict=True)]
        logical = ["" if h else strip_inline_comment(ln) for ln, h in zip(lines, hmask, strict=True)]
        diags: list[Diagnostic] = []
        i = 0
        n = len(lines)
        while i < n:
            m = _RESOURCE_RE.match(logical[i])
            if m is None or m.group(1) not in _PROTECTED_TYPES:
                i += 1
                continue
            rtype, rname = m.group(1), m.group(2)
            start = i
            end = _block_end(masked, i)
            state = _protection_state(logical[start : end + 1])
            if state != "protected":
                detail = (
                    "deletion_protection = false" if state == "disabled" else "no deletion_protection / prevent_destroy"
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
    """Index of the line closing the block opened on `start` (brace-balanced).

    `lines` must already be string/heredoc-masked so braces inside a string
    literal or heredoc body do not throw off the count.

    Returns:
        The index of the closing line, or the last line index if unbalanced.

    """
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

    Returns:
        One of `"protected"`, `"disabled"`, or `"missing"` for the block.

    """
    for line in block:
        m = _DELPROT_RE.match(line)
        if m is not None:
            value = m.group(1).rstrip(",").strip('"')
            return "disabled" if value == "false" else "protected"
    for line in block:
        if _PREVENT_DESTROY_RE.match(line):
            return "protected"
    return "missing"
