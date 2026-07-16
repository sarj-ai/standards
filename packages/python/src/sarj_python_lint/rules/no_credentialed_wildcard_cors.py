"""SARJ024: forbid credentialed wildcard CORS and wildcard-fallback origins.

Two patterns are flagged:

* A `CORSMiddleware` configuration (direct call, or passed positionally as in
  `app.add_middleware(CORSMiddleware, ...)`) whose `allow_origins` contains
  the literal `"*"` AND `allow_credentials=True`. Starlette special-cases the
  combination by reflecting the request's Origin header, so *every* origin
  can make credentialed (cookie / Authorization) requests — cross-site data
  theft, not merely a browser-rejected misconfig.
* Any `allow_origins=` keyword whose value is a conditional expression with a
  `["*"]` in either branch — the wildcard-fallback pattern found live in
  bulbul's `create_app.py`, where an unset settings value silently opened
  CORS to every origin.

Wildcard CORS *without* credentials is legitimate for public and internal
APIs and is deliberately not flagged.

References:
- https://portswigger.net/web-security/cors
- https://fastapi.tiangolo.com/tutorial/cors/
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule


if TYPE_CHECKING:
    from pathlib import Path


class NoCredentialedWildcardCors(Rule):
    """Wildcard CORS origins with credentials, or a wildcard-fallback `allow_origins`."""

    id: str = "no-credentialed-wildcard-cors"
    code: str = "SARJ024"
    description: str = (
        "Wildcard CORS origins with `allow_credentials=True`, or a wildcard-fallback "
        "`allow_origins` conditional."
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
            for kw in node.keywords:
                if kw.arg != "allow_origins" or not isinstance(kw.value, ast.IfExp):
                    continue
                if _contains_wildcard(kw.value.body) or _contains_wildcard(kw.value.orelse):
                    diags.append(
                        Diagnostic(
                            path=path,
                            line=kw.value.lineno,
                            col=kw.value.col_offset + 1,
                            code=self.code,
                            message=(
                                "`allow_origins` conditional falls back to a wildcard "
                                '`["*"]` — an unset/misread setting silently opens CORS '
                                "to every origin; make the fallback explicit and "
                                "non-wildcard."
                            ),
                        )
                    )
            if (
                _is_cors_call(node)
                and _has_wildcard_origins(node)
                and _has_credentials_true(node)
            ):
                diags.append(
                    Diagnostic(
                        path=path,
                        line=node.lineno,
                        col=node.col_offset + 1,
                        code=self.code,
                        message=(
                            'Wildcard `allow_origins=["*"]` with `allow_credentials=True` '
                            "lets any origin make credentialed requests (Starlette "
                            "reflects the Origin header) — list explicit origins."
                        ),
                    )
                )
        return diags


def _is_cors_call(node: ast.Call) -> bool:
    """True if this call configures CORSMiddleware.

    Matches a direct `CORSMiddleware(...)` construction and the wrapped forms
    where the class is passed positionally: `app.add_middleware(CORSMiddleware,
    ...)`, `Middleware(CORSMiddleware, ...)`.
    """
    if _is_cors_name(node.func):
        return True
    return any(_is_cors_name(arg) for arg in node.args)


def _is_cors_name(expr: ast.expr) -> bool:
    """True for `CORSMiddleware` as a bare name or a module attribute."""
    if isinstance(expr, ast.Name):
        return expr.id == "CORSMiddleware"
    return isinstance(expr, ast.Attribute) and expr.attr == "CORSMiddleware"


def _has_wildcard_origins(node: ast.Call) -> bool:
    return any(
        kw.arg == "allow_origins" and _contains_wildcard(kw.value) for kw in node.keywords
    )


def _has_credentials_true(node: ast.Call) -> bool:
    return any(
        kw.arg == "allow_credentials"
        and isinstance(kw.value, ast.Constant)
        and kw.value.value is True
        for kw in node.keywords
    )


def _contains_wildcard(node: ast.expr) -> bool:
    """True if `node` is the literal `"*"` or a list/tuple/set containing it."""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str) and node.value == "*"
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return any(
            isinstance(elt, ast.Constant) and isinstance(elt.value, str) and elt.value == "*"
            for elt in node.elts
        )
    return False
