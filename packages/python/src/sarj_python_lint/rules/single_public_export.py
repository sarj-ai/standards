"""SARJ022: a module whose members are all private except ONE public
top-level definition must be named after that export.

Public = a top-level `class` / `def` / `async def` whose name has no leading
underscore. Constants (ALL_CAPS assignments), `__all__`, and imports are
ignored — the rule governs behavior definitions, not values.

Fires only on **filename mismatch**: the module has exactly one public
def/class and its snake_case form differs from the module stem
(`MultiprocJanitor` -> `multiproc_janitor.py`, `load_call_data` ->
`load_call_data.py`). Modules with several public definitions are out of
scope — the rule rewards the single-export shape, it does not mandate it.

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
    description: str = "A module with a single public def/class must be named after that export."

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
        if len(public_defs) != 1:
            return []

        diags: list[Diagnostic] = []
        primary = public_defs[0]
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
