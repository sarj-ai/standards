"""SARJ202: flag comment cruft in Terraform / IaC — commented-out code and banners.

The same self-documenting standard the Python/TS linters enforce, for `.tf` and
config files. Two deterministic shapes carry no rationale and are pure noise:

1. Commented-out HCL — a standalone comment that is really a disabled resource,
   block, or attribute:
       # resource "google_storage_bucket" "old" {
       # ttl = 3600
   Delete it; Terraform state and git history remember.

2. Section-banner / divider comments:
       # ============================================================
       # ------------------------------------------------------------
   Split the file or use real block structure instead of ASCII rules.

Prose "why" comments are NOT flagged. Directive comments are ignored:
`# sarj-noqa`, `# tflint-ignore`, `# checkov:skip`, `# nosec`, `# TODO`,
`# FIXME`, `# yaml-language-server`, shebangs, and `# terraform:`.

Suppress an intentional case with `# sarj-noqa: SARJ202 — <reason>`.
"""

from __future__ import annotations

import re
from pathlib import Path

from sarj_iac_lint.rule_base import Diagnostic, Rule

_COMMENT_RE = re.compile(r"^(\s*)(#|//)\s?(.*)$")

_DIRECTIVE_PREFIXES = (
    "sarj-noqa",
    "tflint-ignore",
    "tflint:",
    "checkov:",
    "nosec",
    "terraform:",
    "yaml-language-server",
    "todo",
    "fixme",
    "hack",
    "noqa",
    "!",
)

_BANNER_FULL_RE = re.compile(r"^[-=#*~_+.\s]{4,}$")
_BANNER_RUN_RE = re.compile(r"={4,}|-{4,}|#{4,}|\*{4,}|~{4,}")

_HCL_CODE_RE = re.compile(
    r"^(?:resource|data|module|variable|output|provider|locals|terraform|"
    r'backend|dynamic|moved)\s+["{]'
    # attribute assignment whose RHS looks like an HCL value (not English prose
    # such as `deploy = provision the stack` in a comment legend).
    r'|^[A-Za-z_][\w-]*\s*=(?!=)\s*(?:["\'\[{]|\d|true\b|false\b|null\b'
    r"|var\.|local\.|module\.|data\.|[A-Za-z_][\w]*\.|[a-z_][\w]*\()"
    r"|^[A-Za-z_][\w-]*\s*\{$"  # block opener
    r"|^\}\s*$"  # block closer
)


class NoCommentCruft(Rule):
    """Commented-out HCL or a section-banner comment in an IaC file."""

    id = "no-comment-cruft"
    code = "SARJ202"
    description = (
        "Commented-out Terraform/IaC or a section-banner comment — delete it; "
        "code carries the what, comments only the why."
    )

    def check(self, path: Path, source: str) -> list[Diagnostic]:
        # Commented-out-code detection runs on real HCL only. `.tfvars` is
        # excluded: a block of commented `key = ""` lines there is a conventional
        # menu of optional inputs, not dead code. Banners are flagged everywhere.
        detect_code = str(path).endswith((".tf", ".tf.json", ".hcl"))
        diags: list[Diagnostic] = []
        for lineno, raw in enumerate(source.splitlines(), start=1):
            m = _COMMENT_RE.match(raw)
            if m is None:
                continue
            indent, _marker, body = m.group(1), m.group(2), m.group(3).strip()
            if not body or _is_directive(body):
                continue
            msg = self._classify(body, detect_code)
            if msg is not None:
                diags.append(
                    Diagnostic(
                        path=path,
                        line=lineno,
                        col=len(indent) + 1,
                        code=self.code,
                        message=msg,
                    )
                )
        return diags

    def _classify(self, body: str, is_hcl: bool) -> str | None:
        if _is_banner(body):
            return "Section-banner / divider comment — use real structure, not ASCII rules."
        if is_hcl and _HCL_CODE_RE.match(body):
            return (
                "Commented-out Terraform — delete it; state and git history remember."
            )
        return None


def _is_directive(body: str) -> bool:
    low = body.lower()
    return any(low.startswith(p) for p in _DIRECTIVE_PREFIXES)


def _is_banner(body: str) -> bool:
    if _BANNER_FULL_RE.match(body):
        return True
    return bool(_BANNER_RUN_RE.search(body))
