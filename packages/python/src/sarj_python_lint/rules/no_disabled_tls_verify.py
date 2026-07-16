"""SARJ022: detect `verify=False` on httpx/requests calls.

`verify=False` disables TLS certificate verification: the client completes a
handshake with whoever answers, so the connection is still encrypted but no
longer authenticated — an active man-in-the-middle can read and rewrite
everything. That defeats the point of TLS entirely.

Motivation: two live findings in noura-be (the vision_bank v2 `http_client`),
where httpx clients were constructed with `verify=False` to paper over a
partner-gateway certificate problem and verification was never re-enabled.

Scope is deliberately narrow (per review decision): only the `verify` keyword
on calls whose receiver chain syntactically resolves to `httpx` or `requests`
— module-level helpers, client constructors, and inline
`requests.Session().get(...)`-style chains. Custom-wrapper kwargs such as
`ssl_verify=...` and lower-level knobs like `ssl.CERT_NONE` are out of scope:
resolving those reliably needs type information a syntactic linter lacks.

References:
- https://www.python-httpx.org/advanced/ssl/
- https://owasp.org/www-community/attacks/Manipulator-in-the-middle_attack
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule


if TYPE_CHECKING:
    from pathlib import Path


# Callables on the httpx module that accept `verify=`.
_HTTPX_CALLEES = frozenset(
    {"Client", "AsyncClient", "get", "post", "put", "patch", "delete", "request", "stream"}
)

# Callables on the requests module that accept `verify=`.
_REQUESTS_CALLEES = frozenset({"get", "post", "put", "patch", "delete", "request"})

# Request methods on a client/session instance in an inline chain like
# `requests.Session().get(...)` or `httpx.Client().post(...)`.
_INSTANCE_METHODS = frozenset({"get", "post", "put", "patch", "delete", "request", "stream"})

_HTTPX_CLIENT_CTORS = frozenset({"Client", "AsyncClient"})


class NoDisabledTlsVerify(Rule):
    """`verify=False` on an httpx/requests call — disables TLS certificate verification."""

    id: str = "no-disabled-tls-verify"
    code: str = "SARJ022"
    description: str = (
        "`verify=False` on an httpx/requests call disables TLS certificate verification."
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
            if not _is_http_lib_call(node.func):
                continue
            for kw in node.keywords:
                if kw.arg != "verify":
                    continue
                if isinstance(kw.value, ast.Constant) and kw.value.value is False:
                    diags.append(
                        Diagnostic(
                            path=path,
                            line=kw.value.lineno,
                            col=kw.value.col_offset + 1,
                            code=self.code,
                            message=(
                                "`verify=False` disables TLS certificate verification, "
                                "so the connection is MITM-able — fix the certificate "
                                "chain or add `# sarj-noqa: SARJ022 — <reason>`."
                            ),
                        )
                    )
        return diags


def _is_http_lib_call(func: ast.expr) -> bool:
    """True if the callee resolves syntactically to httpx/requests.

    Recognises `httpx.<callee>(...)`, `requests.<callee>(...)`, and inline
    client/session chains (`requests.Session().get(...)`). Variables holding a
    client are not resolvable without type information, so they don't trigger.
    """
    if not isinstance(func, ast.Attribute):
        return False
    receiver = func.value
    if isinstance(receiver, ast.Name):
        if receiver.id == "httpx":
            return func.attr in _HTTPX_CALLEES
        if receiver.id == "requests":
            return func.attr in _REQUESTS_CALLEES
        return False
    if isinstance(receiver, ast.Call) and func.attr in _INSTANCE_METHODS:
        return _is_client_constructor(receiver.func)
    return False


def _is_client_constructor(func: ast.expr) -> bool:
    """True for `httpx.Client` / `httpx.AsyncClient` / `requests.Session`."""
    if not isinstance(func, ast.Attribute) or not isinstance(func.value, ast.Name):
        return False
    if func.value.id == "httpx":
        return func.attr in _HTTPX_CLIENT_CTORS
    return func.value.id == "requests" and func.attr == "Session"
