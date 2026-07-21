"""SARJ024: a long string literal repeated within one module — extract a named constant.

The same 40+ character string literal appearing two or more times in a module
(SQL column lists, user-facing error messages, log lines, spoken prompts) is a
maintenance hazard: when one copy is edited the others silently drift. Derived
from the magic-values audit corpus ("Repeated Complex String Literal"). The fix
is a single module-level constant referenced from every use site.

Only exact, standalone string constants count:

- f-string fragments (`ast.Constant` nodes inside a `JoinedStr`) are ignored —
  two f-strings sharing a prefix are not extractable as one constant.
- Docstrings (first-statement strings of a module/class/function) are ignored.
- Strings under an `examples=` keyword argument are ignored — pydantic/FastAPI
  `Field(examples=[...])` values are OpenAPI documentation scaffolding that is
  deliberately repeated across sibling models (bulbul calibration FP class).
- Strings shorter than 40 characters are ignored; short repeats ("utf-8",
  status slugs) are usually deliberate and belong to other rules (SARJ006).

Each occurrence after the first gets its own diagnostic, so a deliberate
duplicate can be suppressed per-line with `# sarj-noqa: SARJ024 — <reason>`.

Skipped entirely: `conftest.py`, test files (`test_*.py` or under a `tests/`
directory) — fixtures legitimately repeat literal payloads.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule, parse_or_none


if TYPE_CHECKING:
    from pathlib import Path


_MIN_LENGTH = 40
_MIN_OCCURRENCES = 2
_PREVIEW_LENGTH = 40


class NoRepeatedStringLiteral(Rule):
    """A 40+ char string literal repeated in a module must become a named constant."""

    id: str = "no-repeated-string-literal"
    code: str = "SARJ024"
    description: str = "Long string literal repeated in one module — extract a module-level constant."

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        if _is_skipped_path(path):
            return []
        tree = parse_or_none(path, source)
        if tree is None:
            return []

        excluded = _fstring_fragments(tree) | _docstring_nodes(tree) | _example_values(tree)
        occurrences: dict[str, list[ast.Constant]] = defaultdict(list)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and len(node.value) >= _MIN_LENGTH
                and id(node) not in excluded
            ):
                occurrences[node.value].append(node)

        diags: list[Diagnostic] = []
        for value, nodes in occurrences.items():
            if len(nodes) < _MIN_OCCURRENCES:
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
                        f"string literal {_preview(value)} is repeated "
                        f"(first use at line {first.lineno}) — extract a "
                        f"module-level constant so the copies cannot drift."
                    ),
                )
                for node in repeats
            )
        diags.sort(key=lambda d: (d.line, d.col))
        return diags


def _fstring_fragments(tree: ast.Module) -> set[int]:
    return {id(value) for node in ast.walk(tree) if isinstance(node, ast.JoinedStr) for value in node.values}


def _example_values(tree: ast.Module) -> set[int]:
    nodes: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg == "examples":
                nodes.update(id(child) for child in ast.walk(kw.value) if isinstance(child, ast.Constant))
    return nodes


def _docstring_nodes(tree: ast.Module) -> set[int]:
    nodes: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = node.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            nodes.add(id(body[0].value))
    return nodes


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
