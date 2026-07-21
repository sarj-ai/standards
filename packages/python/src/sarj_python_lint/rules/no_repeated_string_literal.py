"""SARJ024: a structured string literal repeated across functions — extract a named constant.

The same long, *structured* string literal appearing in two or more different
functions of a module is a real maintenance hazard: when one copy is edited the
others silently drift, and (unlike SQL/log/prompt scaffolding) the strings that
qualify here cannot plausibly be equal by coincidence. Derived from the
magic-values audit corpus ("Repeated Complex String Literal").

The rule is deliberately narrow — it fires only where cross-site drift is a
genuine bug, never on coincidentally-equal prose. Three filters combine:

1. **Structured only.** A literal qualifies only if it carries structural signal
   that makes coincidental equality near-impossible:
   - it contains a newline (multi-line SQL / prompt templates), OR
   - it matches an *uppercase* SQL keyword (`SELECT`, `FROM`, `WHERE`, …) —
     matched case-sensitively so prose ("...criteria *from* the prompt") does
     not trip it, only real SQL does, OR
   - it is a bare snake_case / dotted identifier (`^[a-z_][a-z0-9_.]*$`), i.e. a
     DB constraint / index / key name reused across statements.
   Plain user-facing error messages, log lines, and spoken prompts carry none of
   these — two different-intent messages that happen to be equal (e.g. a
   `get_user_error_message` mapping two distinct error codes to one sentence) are
   *not* flagged, so a shared constant can never wrongly couple them.

2. **Cross-function only.** The occurrences must span at least two distinct
   enclosing functions/methods. Two uses inside one function (or several
   module-level constants) are edited together and moving them to the module top
   buys no drift protection — that is pure locality loss, so it is excluded.

3. **Exclusions.** f-string fragments (`ast.Constant` inside `JoinedStr`),
   docstrings (first statement of module/class/function), and strings under an
   OpenAPI/pydantic scaffolding keyword (`examples=`, `description=`, `title=`,
   `summary=`) — the latter are documentation scaffolding deliberately repeated
   across sibling models (`Field(description=...)` on parallel schemas), not code
   that drifts.

Each occurrence after the first gets its own diagnostic, so a deliberate
duplicate can be suppressed per-line with `# sarj-noqa: SARJ024 — <reason>`.

Skipped entirely: `conftest.py`, test files (`test_*.py` or under a `tests/`
directory) — fixtures legitimately repeat literal payloads.
"""

from __future__ import annotations

import ast
from collections import defaultdict
import re
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule, parse_or_none


if TYPE_CHECKING:
    from pathlib import Path


_MIN_LENGTH = 40
_MIN_OCCURRENCES = 2
_MIN_DISTINCT_SCOPES = 2
_PREVIEW_LENGTH = 40

_SCAFFOLDING_KWARGS = frozenset({"examples", "description", "title", "summary"})

_SQL_KEYWORD_RE = re.compile(
    r"\b(SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|JOIN|VALUES|ON CONFLICT|RETURNING|GROUP BY|ORDER BY)\b"
)
_IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_.]*$")

_MODULE_SCOPE = -1


class NoRepeatedStringLiteral(Rule):
    """A structured string literal repeated across functions must become a named constant."""

    id: str = "no-repeated-string-literal"
    code: str = "SARJ024"
    description: str = "Structured string literal repeated across functions — extract a module-level constant."

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        if _is_skipped_path(path):
            return []
        tree = parse_or_none(path, source)
        if tree is None:
            return []

        occurrences: dict[str, list[ast.Constant]] = defaultdict(list)
        scope_of: dict[int, int] = {}
        excluded: set[int] = set()

        def visit(node: ast.AST, scope: int) -> None:
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                body = node.body
                if (
                    body
                    and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)
                ):
                    excluded.add(id(body[0].value))
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    scope = id(node)
            elif isinstance(node, ast.JoinedStr):
                excluded.update(id(value) for value in node.values)
            elif isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg in _SCAFFOLDING_KWARGS:
                        excluded.update(id(child) for child in ast.walk(kw.value) if isinstance(child, ast.Constant))
            elif (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and len(node.value) >= _MIN_LENGTH
                and id(node) not in excluded
                and _is_structured(node.value)
            ):
                occurrences[node.value].append(node)
                scope_of[id(node)] = scope
            for child in ast.iter_child_nodes(node):
                visit(child, scope)

        visit(tree, _MODULE_SCOPE)

        diags: list[Diagnostic] = []
        for value, nodes in occurrences.items():
            if len(nodes) < _MIN_OCCURRENCES:
                continue
            function_scopes = {scope for n in nodes if (scope := scope_of.get(id(n), _MODULE_SCOPE)) != _MODULE_SCOPE}
            if len(function_scopes) < _MIN_DISTINCT_SCOPES:
                continue
            nodes.sort(key=lambda n: (n.lineno, n.col_offset))
            first, *repeats = nodes
            diags.extend(
                Diagnostic(
                    path=path,
                    line=node.lineno,
                    col=node.col_offset + 1,
                    code=self.code,
                    message=(
                        f"structured string literal {_preview(value)} is repeated across "
                        f"functions (first use at line {first.lineno}) — extract a "
                        f"module-level constant so the copies cannot drift."
                    ),
                )
                for node in repeats
            )
        diags.sort(key=lambda d: (d.line, d.col))
        return diags


def _is_structured(value: str) -> bool:
    return "\n" in value or _SQL_KEYWORD_RE.search(value) is not None or _IDENTIFIER_RE.match(value) is not None


def _preview(value: str) -> str:
    if len(value) <= _PREVIEW_LENGTH:
        return repr(value)
    return repr(value[:_PREVIEW_LENGTH] + "…")


def _is_skipped_path(path: Path) -> bool:
    if path.name == "conftest.py":
        return True
    if path.name.startswith("test_"):
        return True
    return "tests" in path.parts
