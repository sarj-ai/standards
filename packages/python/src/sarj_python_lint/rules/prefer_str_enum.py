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

from sarj_python_lint.rule_base import Diagnostic, Rule, parse_or_none


if TYPE_CHECKING:
    from pathlib import Path


#: Per-variable comparison-cluster accumulator:
#: (first line, first col, all-lowercase-token, distinct literals).
type _ClusterEntry = tuple[int, int, bool, set[str]]


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


class PreferStrEnum(Rule):
    """Choice-shaped str field or string-literal comparison cluster — prefer StrEnum."""

    id: str = "prefer-str-enum"
    code: str = "SARJ006"
    description: str = "Choice-like str field or literal comparison cluster — prefer StrEnum."

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        tree = parse_or_none(path, source)
        if tree is None:
            return []
        diags: list[Diagnostic] = []
        check_clusters = not _is_test_path(path)
        # One DFS handles both triggers. `active` is the comparison-cluster map
        # of the nearest enclosing function, or None when comparisons must be
        # ignored (module level, or inside a nested class/lambda body — matching
        # the old `_walk_own_scope` scope boundaries).
        all_clusters: list[dict[str, _ClusterEntry]] = []
        stack: list[tuple[ast.AST, dict[str, _ClusterEntry] | None]] = [(tree, None)]
        while stack:
            node, active = stack.pop()
            if isinstance(node, ast.ClassDef):
                diags.extend(self._class_field_diags(path, node))
                child_active: dict[str, _ClusterEntry] | None = None
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if check_clusters:
                    child_active = {}
                    all_clusters.append(child_active)
                else:
                    child_active = None
            elif isinstance(node, ast.Lambda):
                child_active = None
            else:
                child_active = active
                if active is not None:
                    if isinstance(node, ast.Compare):
                        _accumulate_compare(active, node)
                    elif isinstance(node, ast.Match):
                        _accumulate_match(active, node)
            stack.extend((child, child_active) for child in ast.iter_child_nodes(node))

        for clusters in all_clusters:
            for key, (line, col, ok, literals) in clusters.items():
                if not ok or len(literals) < _MIN_CLUSTER_SIZE:
                    continue
                diags.append(
                    Diagnostic(
                        path=path,
                        line=line,
                        col=col,
                        code=self.code,
                        message=(f"`{key}` is compared against a closed set of string literals — define a StrEnum"),
                    )
                )
        diags.sort(key=lambda d: (d.line, d.col))
        return diags

    def _class_field_diags(self, path: Path, cls: ast.ClassDef) -> list[Diagnostic]:
        diags: list[Diagnostic] = []
        # Skip enum classes themselves
        if any(_base_name(b) in {"Enum", "StrEnum", "IntEnum"} for b in cls.bases):
            return diags
        # Find string-list class attrs that look like a choices set.
        choices_attrs: set[str] = set()
        for stmt in cls.body:
            if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                target = (
                    stmt.targets[0] if isinstance(stmt, ast.Assign) and stmt.targets else getattr(stmt, "target", None)
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
            ann_text = _annotation_text(stmt.annotation)
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


def _base_name(base: ast.AST) -> str | None:
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return None


def _is_string_collection(node: ast.AST | None) -> bool:
    if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return False
    return all(isinstance(elt, ast.Constant) and isinstance(elt.value, str) for elt in node.elts)


def _is_choice_like_name(name: str) -> bool:
    lowered = name.lower()
    if lowered in CHOICE_NAME_TOKENS:
        return True
    return any(lowered.endswith(f"_{token}") for token in CHOICE_NAME_TOKENS)


def _is_test_path(path: Path) -> bool:
    if path.name.startswith("test_"):
        return True
    return "tests" in path.parts


def _accumulate_compare(clusters: dict[str, _ClusterEntry], node: ast.Compare) -> None:
    extracted = _extract_compare(node)
    if extracted is None:
        return
    key, literals = extracted
    _merge_cluster(clusters, key, literals, (node.lineno, node.col_offset + 1))


def _accumulate_match(clusters: dict[str, _ClusterEntry], node: ast.Match) -> None:
    key = _ref_key(node.subject)
    if key is None:
        return
    literals: list[str] = []
    for case in node.cases:
        literals.extend(_match_pattern_literals(case.pattern))
    if not literals:
        return
    _merge_cluster(clusters, key, literals, (node.lineno, node.col_offset + 1))


def _merge_cluster(clusters: dict[str, _ClusterEntry], key: str, literals: list[str], pos: tuple[int, int]) -> None:
    all_tokens = all(_LOWER_TOKEN_RE.fullmatch(lit) for lit in literals)
    entry = clusters.get(key)
    if entry is not None:
        line, col, ok, seen = entry
        line, col = min((line, col), pos)
        clusters[key] = (line, col, ok and all_tokens, seen | set(literals))
    else:
        clusters[key] = (*pos, all_tokens, set(literals))


def _match_pattern_literals(pattern: ast.pattern) -> list[str]:
    """String-constant literals from a `case` pattern (`MatchValue` / `MatchOr`)."""
    if isinstance(pattern, ast.MatchValue):
        value = _str_const(pattern.value)
        return [value] if value is not None else []
    if isinstance(pattern, ast.MatchOr):
        literals: list[str] = []
        for sub in pattern.patterns:
            literals.extend(_match_pattern_literals(sub))
        return literals
    return []


def _annotation_text(annotation: ast.expr | None) -> str:
    """Unparsed annotation, unwrapping a stringized forward-ref (`x: "str"`)."""
    if annotation is None:
        return ""
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        return annotation.value
    return ast.unparse(annotation)


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
