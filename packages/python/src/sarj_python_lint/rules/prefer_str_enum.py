"""SARJ006: raw `str` used where a closed enumeration is clearly intended.

`Literal["a", "b", "c"]` is acceptable — that's a proper closed set. This rule
flags three shapes of choice-like `str` usage:

1. **Choice-like field name** — a class field annotated raw `str` whose name is
   (or ends with `_` plus) one of the choice-like tokens: `status`, `state`,
   `type`, `kind`, `provider`, `language`, `lang`, `role`, `priority`, `level`,
   `mode`, `category`, `direction`, `environment`, `env`, `tier`, `severity`,
   `channel`, `method`, `strategy`, `format`, `source`, `stage`. Fires whether
   the field is bare (`provider: str`), has a plain default
   (`mode: str = "fast"`), or a pydantic default (`mode: str = Field(default="fast")`).
2. **Sibling choices attribute** — a class with a string-collection attribute
   named `choices`/`states`/`statuses`/`values`/`allowed` flags its raw-`str`
   fields (the collection is the enum that should exist).
3. **Comparison cluster** — within one function, the same variable or attribute
   compared (`==`/`!=`/`in (...)`) against 2+ distinct short lowercase string
   literals (all matching `^[a-z][a-z0-9_-]{0,30}$`). One diagnostic on the
   first comparison. F-string and attribute comparands and subscripted
   left-hand sides are ignored, and test files
   (`test_*.py` / under a `tests/` directory) are skipped.

Replace with:
    class Status(StrEnum):
        ACTIVE = "active"
        INACTIVE = "inactive"

References:
- https://docs.python.org/3/library/enum.html#enum.StrEnum
- https://docs.pydantic.dev/latest/concepts/types/#enums
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule


if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


#: Field / variable name tokens that strongly suggest a closed enumeration.
#: Kept deliberately HIGH-PRECISION — only words that are almost always a fixed
#: set. Broader/free-form-prone tokens (type, provider, level, mode, category,
#: channel, method, strategy, format, source, language, environment, …) were
#: removed: they over-fired on free-form strings. Those cases are still caught
#: when corroborated — via a sibling `choices`/`states` attribute or a
#: comparison cluster against literal values.
CHOICE_NAME_TOKENS = frozenset(
    {
        "status",
        "state",
        "kind",
        "role",
        "priority",
        "severity",
        "direction",
        "tier",
        "stage",
    }
)

#: Sibling class attributes whose presence marks all raw-str fields as choice-like.
CHOICES_ATTR_NAMES = frozenset({"choices", "states", "statuses", "values", "allowed"})

#: A "short lowercase token" — the shape enum member values take.
_LOWER_TOKEN_RE = re.compile(r"^[a-z][a-z0-9_-]{0,30}$")

#: How many distinct literals a variable must be compared against to fire.
_MIN_CLUSTER_SIZE = 2

#: Scope boundaries we do not descend into when attributing comparisons to a function.
_NESTED_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


class PreferStrEnum(Rule):
    """Choice-shaped str field or string-literal comparison cluster — prefer StrEnum."""

    id: str = "prefer-str-enum"
    code: str = "SARJ006"
    description: str = "Choice-like str field or literal comparison cluster — prefer StrEnum."

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return []
        diags: list[Diagnostic] = []
        diags.extend(self._check_class_fields(path, tree))
        if not _is_test_path(path):
            diags.extend(self._check_comparison_clusters(path, tree))
        diags.sort(key=lambda d: (d.line, d.col))
        return diags

    def _check_class_fields(self, path: Path, tree: ast.AST) -> list[Diagnostic]:
        diags: list[Diagnostic] = []
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            # Skip enum classes themselves
            if any(_base_name(b) in {"Enum", "StrEnum", "IntEnum"} for b in cls.bases):
                continue
            # Find string-list class attrs that look like a choices set.
            choices_attrs: set[str] = set()
            for stmt in cls.body:
                if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                    target = (
                        stmt.targets[0]
                        if isinstance(stmt, ast.Assign) and stmt.targets
                        else getattr(stmt, "target", None)
                    )
                    if not isinstance(target, ast.Name):
                        continue
                    val = getattr(stmt, "value", None)
                    if _is_string_collection(val) and target.id.lower() in CHOICES_ATTR_NAMES:
                        choices_attrs.add(target.id)
            # Flag bare-str AnnAssigns
            for stmt in cls.body:
                if not isinstance(stmt, ast.AnnAssign):
                    continue
                if not isinstance(stmt.target, ast.Name):
                    continue
                ann_text = ast.unparse(stmt.annotation) if stmt.annotation else ""
                if ann_text.strip() != "str":
                    continue  # Literal[...] etc. is fine per user L234
                # Heuristic: there's a nearby choices list OR the field name
                # is (or ends with) a choice-like token.
                name = stmt.target.id
                if choices_attrs or _is_choice_like_name(name):
                    diags.append(
                        Diagnostic(
                            path=path,
                            line=stmt.lineno,
                            col=stmt.col_offset + 1,
                            code=self.code,
                            message=(
                                f"`{name}: str` looks like a choice field — "
                                "prefer `StrEnum`. (`Literal[...]` is also acceptable.)"
                            ),
                        )
                    )
        return diags

    def _check_comparison_clusters(self, path: Path, tree: ast.AST) -> list[Diagnostic]:
        diags: list[Diagnostic] = []
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            # key -> (first line, first col, all-lowercase-token, distinct literals)
            clusters: dict[str, tuple[int, int, bool, set[str]]] = {}
            for node in _walk_own_scope(func):
                if not isinstance(node, ast.Compare):
                    continue
                extracted = _extract_compare(node)
                if extracted is None:
                    continue
                key, literals = extracted
                all_tokens = all(_LOWER_TOKEN_RE.fullmatch(lit) for lit in literals)
                pos = (node.lineno, node.col_offset + 1)
                if key in clusters:
                    line, col, ok, seen = clusters[key]
                    line, col = min((line, col), pos)
                    clusters[key] = (line, col, ok and all_tokens, seen | set(literals))
                else:
                    clusters[key] = (*pos, all_tokens, set(literals))
            for key, (line, col, ok, literals) in clusters.items():
                if not ok or len(literals) < _MIN_CLUSTER_SIZE:
                    continue
                diags.append(
                    Diagnostic(
                        path=path,
                        line=line,
                        col=col,
                        code=self.code,
                        message=(
                            f"`{key}` is compared against a closed set of "
                            "string literals — define a StrEnum"
                        ),
                    )
                )
        return diags


def _base_name(base: ast.AST) -> str | None:
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return None


def _is_string_collection(node: ast.AST | None) -> bool:
    if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return False
    return all(
        isinstance(elt, ast.Constant) and isinstance(elt.value, str)
        for elt in node.elts
    )


def _is_choice_like_name(name: str) -> bool:
    lowered = name.lower()
    if lowered in CHOICE_NAME_TOKENS:
        return True
    return any(lowered.endswith(f"_{token}") for token in CHOICE_NAME_TOKENS)


def _is_test_path(path: Path) -> bool:
    if path.name.startswith("test_"):
        return True
    return "tests" in path.parts


def _walk_own_scope(func: ast.AST) -> Iterator[ast.AST]:
    """Yield descendants of `func` without descending into nested scopes."""
    stack: list[ast.AST] = list(ast.iter_child_nodes(func))
    while stack:
        node = stack.pop()
        if isinstance(node, _NESTED_SCOPES):
            continue
        yield node
        stack.extend(ast.iter_child_nodes(node))


def _extract_compare(node: ast.Compare) -> tuple[str, list[str]] | None:
    """Return (variable key, string literals) for an enum-shaped comparison.

    Handles `x == "a"`, `"a" == x` (yoda), `x != "a"`, and
    `x in ("a", "b")` / `x not in {...}` where every element is a string
    constant. The left-hand side must be a plain name or attribute chain —
    subscripts (dict keys), calls, f-strings, etc. are excluded.
    """
    if len(node.ops) != 1 or len(node.comparators) != 1:
        return None
    op = node.ops[0]
    left, right = node.left, node.comparators[0]
    if isinstance(op, (ast.Eq, ast.NotEq)):
        if _ref_key(left) is not None and _str_const(right) is not None:
            ref, lit = left, right
        elif _str_const(left) is not None and _ref_key(right) is not None:
            ref, lit = right, left
        else:
            return None
        key = _ref_key(ref)
        value = _str_const(lit)
        if key is None or value is None:  # pragma: no cover — guarded above
            return None
        return key, [value]
    if isinstance(op, (ast.In, ast.NotIn)):
        key = _ref_key(left)
        if key is None:
            return None
        if not isinstance(right, (ast.Tuple, ast.List, ast.Set)) or not right.elts:
            return None
        values: list[str] = []
        for elt in right.elts:
            value = _str_const(elt)
            if value is None:
                return None
            values.append(value)
        return key, values
    return None


def _ref_key(node: ast.AST) -> str | None:
    """A stable key for a plain name or dotted attribute chain; else None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        inner = _ref_key(node.value)
        if inner is None:
            return None
        return f"{inner}.{node.attr}"
    return None


def _str_const(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None
