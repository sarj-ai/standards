"""SARJ205: flag an `access_config` block — it gives a Compute VM a public IP.

An empty (or default) `access_config {}` inside a `network_interface` assigns an
ephemeral **external** IP to the instance. Most workloads here are egress-only
(they dial out to LiveKit / APIs and need no inbound), so a public IP is
unnecessary attack surface and cost — route egress through Cloud NAT instead.
This is the exact thing the reviewer repeatedly flagged ("you don't need a
public ip for worker").

    # flagged
    network_interface {
      network = var.network
      access_config {}
    }

    # ok (egress via Cloud NAT, no external IP)
    network_interface {
      network = var.network
    }

If the VM genuinely needs inbound from the internet, suppress with
`# sarj-noqa: SARJ205 — <reason>` on the `access_config` line.
"""

from __future__ import annotations

import re
from pathlib import Path

from sarj_iac_lint.rule_base import Diagnostic, Rule

_ACCESS_CONFIG_RE = re.compile(r"^\s*access_config\b")


class NoVmPublicIp(Rule):
    """`access_config` block assigns a Compute VM a public IP — prefer Cloud NAT."""

    id = "no-vm-public-ip"
    code = "SARJ205"
    description = (
        "access_config gives a Compute VM an external IP — egress-only workloads "
        "should use Cloud NAT, not a public IP (unnecessary attack surface)."
    )

    def check(self, path: Path, source: str) -> list[Diagnostic]:
        if not str(path).endswith((".tf", ".tf.json", ".hcl")):
            return []
        diags: list[Diagnostic] = []
        for lineno, line in enumerate(source.splitlines(), start=1):
            code = _strip_comment(line)
            m = _ACCESS_CONFIG_RE.match(code)
            if m is not None:
                diags.append(
                    Diagnostic(
                        path=path,
                        line=lineno,
                        col=len(line) - len(line.lstrip()) + 1,
                        code=self.code,
                        message=(
                            "access_config assigns the VM an external IP — egress-only "
                            "workloads should use Cloud NAT, not a public IP."
                        ),
                    )
                )
        return diags


def _strip_comment(line: str) -> str:
    for marker in ("#", "//"):
        idx = line.find(marker)
        if idx != -1:
            line = line[:idx]
    return line
