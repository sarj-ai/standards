"""SARJ023: require an explicit `timeout=` on httpx clients and one-shot calls.

Honesty note: httpx is not a hang-forever footgun — unlike `requests`, it
applies a 5-second default timeout to connect/read/write/pool. This is an
explicit-policy rule, not a bug-class rule: for LLM and voice workloads the
5 s default is wrong in both directions (far too short for LLM generation and
batch calls, which then die mid-request; longer than acceptable on
latency-sensitive voice paths). Every client construction and one-shot call
must therefore state its timeout policy — `timeout=None` (never time out) is
accepted because it is explicit.

Conservative trigger: a call carrying a `**kwargs` spread is never flagged,
since the spread may supply `timeout`.

Ruff's S113 ("request without timeout") covers `requests` only, not httpx, so
this rule does not duplicate it.

References:
- https://www.python-httpx.org/advanced/timeouts/
- https://docs.astral.sh/ruff/rules/request-without-timeout/
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule


if TYPE_CHECKING:
    from pathlib import Path


# Client constructors and one-shot request helpers on the httpx module.
_TIMEOUT_REQUIRED_CALLEES = frozenset(
    {"Client", "AsyncClient", "get", "post", "put", "patch", "delete", "request"}
)


class HttpxTimeoutRequired(Rule):
    """httpx client construction or one-shot call without an explicit `timeout=`."""

    id: str = "httpx-timeout-required"
    code: str = "SARJ023"
    description: str = (
        "httpx client or one-shot call without an explicit `timeout=` — state the policy."
    )

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return []
        diags: list[Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "httpx"
                and func.attr in _TIMEOUT_REQUIRED_CALLEES
            ):
                continue
            # A `**spread` may carry timeout — stay conservative and skip.
            if any(kw.arg is None for kw in node.keywords):
                continue
            if any(kw.arg == "timeout" for kw in node.keywords):
                continue
            diags.append(
                Diagnostic(
                    path=path,
                    line=node.lineno,
                    col=node.col_offset + 1,
                    code=self.code,
                    message=(
                        f"`httpx.{func.attr}` without an explicit `timeout=` — the "
                        "implicit 5 s default is a policy decision made by omission; "
                        "pass `timeout=` (an httpx.Timeout, a float, or None) "
                        "deliberately."
                    ),
                )
            )
        return diags
