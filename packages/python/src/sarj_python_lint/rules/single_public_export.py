"""SARJ022: a module opted into this rule must expose exactly one public
top-level definition, and the filename must be that export's snake_case name.

Public = a top-level `class` / `def` / `async def` whose name has no leading
underscore. Everything else in the module (helpers, constants, regexes) should
be underscore-private or live on the exported class. Constants (ALL_CAPS
assignments), `__all__`, and imports are ignored — the rule governs behavior
definitions, not values.

Fires on:
1. **Extra public definition** — every public def/class beyond the first.
2. **Filename mismatch** — the single public export's snake_case form differs
   from the module stem (`MultiprocJanitor` -> `multiproc_janitor.py`,
   `load_call_data` -> `load_call_data.py`).

Skipped entirely: `__init__.py`, `conftest.py`, test files (`test_*.py` or
under a `tests/` directory), and modules with zero public definitions
(pure-constant/type modules).
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule, parse_or_none


if TYPE_CHECKING:
    from pathlib import Path


_CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")

_SKIPPED_FILENAMES = frozenset({"__init__.py", "conftest.py"})


class SinglePublicExport(Rule):
    """Module must expose one public def/class, named after the file."""

    id: str = "single-public-export"
    code: str = "SARJ022"
    description: str = "One public top-level def/class per module; filename must be its snake_case name."

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        if _is_skipped_path(path):
            return []
        tree = parse_or_none(path, source)
        if tree is None:
            return []

        public_defs = [
            node
            for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_")
        ]
        if not public_defs:
            return []

        diags: list[Diagnostic] = []
        primary, *extras = public_defs
        for node in extras:
            diags.append(
                Diagnostic(
                    path=path,
                    line=node.lineno,
                    col=node.col_offset + 1,
                    code=self.code,
                    message=(
                        f"`{node.name}` is a second public definition — this module already "
                        f"exports `{primary.name}`. Make it private or move it to its own module."
                    ),
                )
            )

        expected_stem = _snake_case(primary.name)
        if path.stem != expected_stem:
            diags.append(
                Diagnostic(
                    path=path,
                    line=primary.lineno,
                    col=primary.col_offset + 1,
                    code=self.code,
                    message=(
                        f"module is named `{path.name}` but its public export is "
                        f"`{primary.name}` — rename the file to `{expected_stem}.py`."
                    ),
                )
            )
        return diags


def _snake_case(name: str) -> str:
    return _CAMEL_BOUNDARY_RE.sub("_", name).lower()


def _is_skipped_path(path: Path) -> bool:
    if path.name in _SKIPPED_FILENAMES:
        return True
    if path.name.startswith("test_"):
        return True
    return "tests" in path.parts
