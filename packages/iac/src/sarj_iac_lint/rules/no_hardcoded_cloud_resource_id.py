"""SARJ204: flag a hardcoded GCP project id on a resource attribute in Terraform.

A literal project id baked into a resource's `project = "..."` is
environment-specific config masquerading as code: it can't be reused across
prod/preview/dev and silently diverges when copied. The house pattern is
`project = var.project` (every real bulbul resource does this); the literal
value lives in the per-env `terraform.tfvars`.

    # flagged (resource attribute in a .tf file)
    resource "google_cloud_run_service" "x" {
      project = "sarj-bulbul"
    }

    # ok
    project = var.project

Scope is deliberately narrow to avoid false positives: only `.tf`/`.hcl` files
are inspected (NOT `.tfvars` — that is the correct home for env-specific
literals), and only a `project`/`project_id` attribute assigned a literal
GCP-project-shaped string (with a hyphen). Regions/zones and endpoints are not
flagged. Suppress with `# sarj-noqa: SARJ204 — <reason>`.
"""

from __future__ import annotations

import re
from pathlib import Path

from sarj_iac_lint.rule_base import Diagnostic, Rule

_PROJECT_ATTR_RE = re.compile(
    r'^\s*project(?:_id)?\s*=\s*"([a-z][a-z0-9-]{4,28}[a-z0-9])"'
)


class NoHardcodedCloudResourceId(Rule):
    """Hardcoded GCP project id on a resource attribute — use var.project."""

    id = "no-hardcoded-cloud-resource-id"
    code = "SARJ204"
    description = (
        'Hardcoded GCP project id on a resource `project = "..."` — use '
        "var.project; the literal value belongs in the per-env terraform.tfvars."
    )

    def check(self, path: Path, source: str) -> list[Diagnostic]:
        if not str(path).endswith((".tf", ".tf.json", ".hcl")):
            return []
        diags: list[Diagnostic] = []
        for lineno, line in enumerate(source.splitlines(), start=1):
            code = _strip_comment(line)
            m = _PROJECT_ATTR_RE.match(code)
            if m is not None and "-" in m.group(1):
                diags.append(
                    Diagnostic(
                        path=path,
                        line=lineno,
                        col=code.index(m.group(1)) + 1,
                        code=self.code,
                        message=(
                            f'hardcoded project id "{m.group(1)}" — use var.project '
                            "(the literal belongs in the env terraform.tfvars)."
                        ),
                    )
                )
        return diags

    def _diag(self, path: Path, line: int, col: int, msg: str) -> Diagnostic:
        return Diagnostic(
            path=path, line=line, col=col + 1, code=self.code, message=msg
        )


def _strip_comment(line: str) -> str:
    """Drop a trailing `#`/`//` comment, ignoring markers inside string literals
    (so the `//` in `"http://host"` is not mistaken for a comment)."""
    in_str = False
    quote = ""
    for i, c in enumerate(line):
        if in_str:
            if c == quote:
                in_str = False
        elif c in ('"', "'"):
            in_str, quote = True, c
        elif c == "#":
            return line[:i]
        elif c == "/" and i + 1 < len(line) and line[i + 1] == "/":
            return line[:i]
    return line
