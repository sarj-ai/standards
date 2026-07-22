"""SARJ030: flag an external JSON payload consumed untyped.

A `.json()` call (no args) or a `json.loads(...)` / `json.load(...)` result used
*directly* — subscripted (`["k"]`), `.get(...)`-ed, or attribute-chained — reaches
into an external payload's shape without ever parsing it into a pydantic model.
When the vendor changes that shape the access breaks silently at runtime instead
of at a validated boundary.

    resp.json()["access_token"]        # fires
    resp.json().get("data")            # fires
    (await client.get(u)).json()["k"]  # fires
    json.loads(body)["id"]             # fires

Parse the payload first: `Token.model_validate(resp.json())`, then read typed
attributes off the model.

This is an access-shape signal, distinct from the annotation-based SARJ008 /
ANN401 (`dict[str, Any]` parameters): those catch an untyped *type*, this catches
an untyped *use* of a live external response with no annotation at all.

Deliberately NOT flagged (keeps false positives at zero):
- assign-then-subscript (`d = resp.json(); d["k"]`) — only DIRECT chaining off the
  `.json()` / `json.loads()` call is tracked; a bound name could be anything,
- a `.json(...)` call WITH arguments — that receiver is not the payload accessor,
- the payload passed to a parser (`Model.model_validate(resp.json())`) rather than
  subscripted — that IS the parse we want,
- a plain dict/list literal subscript (`{"a": 1}["a"]`),
- a bare `.json` attribute that is never called, and `json.dumps(...)`.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule, parse_or_none


if TYPE_CHECKING:
    from pathlib import Path


class JsonResponseNotParsed(Rule):
    """External JSON payload consumed untyped instead of parsed into a model."""

    id: str = "json-response-not-parsed"
    code: str = "SARJ030"
    description: str = (
        "A `.json()` / `json.loads()` result is subscripted, `.get()`-ed, or "
        "attribute-chained directly — parse it into a pydantic model first."
    )

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        tree = parse_or_none(path, source)
        if tree is None:
            return []
        diags: list[Diagnostic] = []
        for node in ast.walk(tree):
            value = _direct_accessed_value(node)
            if value is None or not _is_json_payload_call(value):
                continue
            diags.append(
                Diagnostic(
                    path=path,
                    line=node.lineno,
                    col=node.col_offset + 1,
                    code=self.code,
                    message=(
                        "External JSON payload consumed untyped — parse the "
                        "`.json()` / `json.loads()` result into a pydantic model "
                        "before subscripting or attribute access."
                    ),
                )
            )
        diags.sort(key=lambda d: (d.line, d.col))
        return diags


def _direct_accessed_value(node: ast.AST) -> ast.expr | None:
    """The receiver being read off, if `node` reaches directly into a value.

    Covers the three access shapes — `<value>[...]` (Subscript), `<value>.attr`
    (Attribute, which also covers `<value>.get(...)` since `.get` is an
    attribute), and nothing else. Returns the `<value>` expression, or None.
    """
    if isinstance(node, ast.Subscript):
        return node.value
    if isinstance(node, ast.Attribute):
        return node.value
    return None


def _is_json_payload_call(node: ast.expr) -> bool:
    """True for a JSON-payload-producing call: `<x>.json()` with NO args, or
    `json.loads(...)` / `json.load(...)`.

    A `.json(...)` call with any positional or keyword argument is not the payload
    accessor and is skipped.
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr == "json":
        return not node.args and not node.keywords
    if func.attr in {"loads", "load"}:
        return isinstance(func.value, ast.Name) and func.value.id == "json"
    return False
