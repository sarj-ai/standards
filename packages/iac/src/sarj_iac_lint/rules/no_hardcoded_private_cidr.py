"""SARJ203: flag a hardcoded private (RFC-1918) IP/CIDR in Terraform.

A literal private subnet baked into a `.tf` file (`"10.0.1.0/24"`) is
environment-specific configuration masquerading as code: it can't be reused
across dev/staging/prod, diverges silently when copied, and hides the network
topology from `terraform.tfvars`. Lift it into a variable.

    # flagged
    ip_cidr_range = "10.0.1.0/24"

    # ok
    ip_cidr_range = var.subnet_cidr

Only RFC-1918 private ranges are flagged (10/8, 172.16/12, 192.168/16) — these
are almost always env-specific. Public IPs, `0.0.0.0/0`, loopback, and
documentation ranges are left alone. Comments are skipped. Suppress a deliberate
constant with `# sarj-noqa: SARJ203 — <reason>`.
"""

from __future__ import annotations

import re
from pathlib import Path

from sarj_iac_lint.rule_base import Diagnostic, Rule

_PRIVATE_CIDR_RE = re.compile(
    r"\b(?:"
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r")(?:/\d{1,2})?\b"
)


class NoHardcodedPrivateCidr(Rule):
    """Hardcoded RFC-1918 private IP/CIDR — extract to a variable."""

    id = "no-hardcoded-private-cidr"
    code = "SARJ203"
    description = (
        "Hardcoded private (RFC-1918) IP/CIDR in Terraform — lift it into a "
        "variable so it is not duplicated across environments."
    )

    def check(self, path: Path, source: str) -> list[Diagnostic]:
        if not str(path).endswith((".tf", ".tf.json", ".hcl", ".tfvars")):
            return []
        diags: list[Diagnostic] = []
        for lineno, line in enumerate(source.splitlines(), start=1):
            code = _strip_comment(line)
            for m in _PRIVATE_CIDR_RE.finditer(code):
                diags.append(
                    Diagnostic(
                        path=path,
                        line=lineno,
                        col=m.start() + 1,
                        code=self.code,
                        message=(
                            f"Hardcoded private CIDR/IP `{m.group(0)}` — extract to a "
                            "variable (e.g. var.subnet_cidr) instead of inlining it."
                        ),
                    )
                )
        return diags


def _strip_comment(line: str) -> str:
    """Drop an inline `#` or `//` comment so literals in comments aren't flagged."""
    for marker in ("#", "//"):
        idx = line.find(marker)
        if idx != -1:
            line = line[:idx]
    return line
