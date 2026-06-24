"""SARJ005: flag poor-man's-result shapes — prefer a discriminated union.

Three triggers:

1. **success-bool model** — a pydantic BaseModel with a bool status field plus
   Optional siblings:

       class Result(BaseModel):
           success: bool
           data: Optional[Data] = None
           error: Optional[str] = None

   allows illegal states (success=True with data=None, or success=False with
   data set). Use a discriminated union:

       class Success(BaseModel): data: Data
       class Failure(BaseModel): error: str
       Result = Union[Success, Failure]

2. **bool-tuple result** — a function whose return annotation is a two-element
   `tuple[bool, X]` / `tuple[X, bool]` (also `Tuple[...]` and `X | None`
   payloads): the classic `(ok, value)` poor-man's-result. Model
   success/failure as a discriminated union (e.g. `Ok[T] | Err`) instead of a
   bool-tuple — the bool and the payload can disagree.

3. **nullable cluster with a discriminator** — a pydantic BaseModel or
   dataclass with 3+ `X | None` / `Optional[X]` fields AND a str / StrEnum /
   Literal field named like a discriminator (`status`, `state`, `type`,
   `kind`, `result`, `outcome`):

       class Call(BaseModel):
           status: str
           started_at: datetime | None = None
           ended_at: datetime | None = None
           error: str | None = None

   Split into per-state models in a discriminated union (the CallState
   pattern: `PendingCall | ActiveCall | CompletedCall | FailedCall`) so each
   state carries exactly the fields that are valid for it.

   Query/filter inputs and PATCH-style partial-update DTOs legitimately hold
   many optional fields, so class names matching those conventions
   (`*Input` / `*Params` / `*Filter` / `*Query` / `Update*` / `Patch*` /
   `Upsert*`) are excluded from this trigger.

   A single-value `Literal` tag (e.g. `type: Literal["complete"]`) marks a model
   that is already an arm of a discriminated union, so it is excluded too — a
   multi-value `Literal[...]` is still treated as a poor-man's discriminator.

References:
- https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions
- https://en.wikipedia.org/wiki/Tagged_union
"""

from __future__ import annotations

import ast
from pathlib import Path

from sarj_python_lint.rule_base import Diagnostic, Rule

STATUS_FIELDS = {"success", "ok", "is_success", "succeeded", "successful", "failed", "failure"}
IGNORED_OPTIONAL_FIELDS = {
    "metadata",
    "meta",
    "debug",
    "debug_logs",
    "extra",
    "log",
    "logs",
    "traceback",
    "request_id",
    "trace_id",
}
DISCRIMINATOR_FIELD_NAMES = {"status", "state", "type", "kind", "result", "outcome"}
NULLABLE_CLUSTER_THRESHOLD = 3
# Query/filter inputs and partial-update DTOs are all-optional by design.
DTO_CLASS_NAME_SUFFIXES = ("Input", "Params", "Filter", "Query")
DTO_CLASS_NAME_PREFIXES = ("Update", "Patch", "Upsert")


class PreferDiscriminatedUnion(Rule):
    """Bool-status models, bool-tuple results, status+Optionals — prefer a discriminated union."""

    id = "prefer-discriminated-union"
    code = "SARJ005"
    description = (
        "success:bool + Optionals, tuple[bool, X] results, or status + nullable "
        "cluster — use a discriminated union."
    )

    def check(self, path: Path, source: str) -> list[Diagnostic]:
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return []
        diags: list[Diagnostic] = []
        str_enum_names = _collect_str_enum_names(tree)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                diag = self._check_bool_tuple_return(path, node)
                if diag is not None:
                    diags.append(diag)
                continue
            if not isinstance(node, ast.ClassDef):
                continue
            diag = self._check_class(path, node, str_enum_names)
            if diag is not None:
                diags.append(diag)
        return diags

    def _check_bool_tuple_return(
        self, path: Path, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> Diagnostic | None:
        if not _is_bool_tuple(node.returns):
            return None
        returns_text = ast.unparse(node.returns) if node.returns else ""
        return Diagnostic(
            path=path,
            line=node.lineno,
            col=node.col_offset + 1,
            code=self.code,
            message=(
                f"`{node.name}` returns `{returns_text}` — a (ok, value) bool-tuple. "
                "Model success/failure as a discriminated union "
                "(e.g. `Ok[T] | Err`), not a bool-tuple."
            ),
        )

    def _check_class(
        self, path: Path, node: ast.ClassDef, str_enum_names: set[str]
    ) -> Diagnostic | None:
        is_model = _inherits_basemodel(node)
        is_dc = _is_dataclass(node)
        if not (is_model or is_dc):
            return None
        has_status_bool = False
        has_literal_tag = False
        optional_fields: list[str] = []
        discriminator_fields: list[str] = []
        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign):
                continue
            if not isinstance(stmt.target, ast.Name):
                continue
            name = stmt.target.id
            ann_text = ast.unparse(stmt.annotation) if stmt.annotation else ""
            if name in STATUS_FIELDS and "bool" in ann_text:
                has_status_bool = True
            if name in DISCRIMINATOR_FIELD_NAMES and _is_discriminator_type(
                stmt.annotation, str_enum_names
            ):
                discriminator_fields.append(name)
                if _is_single_value_literal(stmt.annotation):
                    has_literal_tag = True
            if _is_optional(stmt.annotation):
                if name not in IGNORED_OPTIONAL_FIELDS:
                    optional_fields.append(name)
        # Original trigger: bool status field + Optional siblings (BaseModel only).
        if is_model and has_status_bool and len(optional_fields) >= 2:
            return Diagnostic(
                path=path,
                line=node.lineno,
                col=node.col_offset + 1,
                code=self.code,
                message=(
                    f"`{node.name}` has a bool status field plus "
                    f"Optional fields ({', '.join(optional_fields)}). "
                    "Model as `Union[Success, Failure]` to make illegal "
                    "states unrepresentable."
                ),
            )
        # Nullable-cluster trigger: discriminator-ish field + 3 or more nullables.
        # A single-value `Literal` tag (e.g. `type: Literal["complete"]`) marks a
        # model that is already a discriminated-union arm, not a poor-man's result.
        if (
            discriminator_fields
            and len(optional_fields) >= NULLABLE_CLUSTER_THRESHOLD
            and not _is_dto_class_name(node.name)
            and not has_literal_tag
        ):
            return Diagnostic(
                path=path,
                line=node.lineno,
                col=node.col_offset + 1,
                code=self.code,
                message=(
                    f"`{node.name}` has a discriminator-ish field "
                    f"(`{discriminator_fields[0]}`) plus {len(optional_fields)} nullable "
                    f"fields ({', '.join(optional_fields)}). Split into per-state models "
                    "in a discriminated union (the CallState pattern: "
                    "`PendingCall | ActiveCall | CompletedCall | FailedCall`)."
                ),
            )
        return None


def _is_dto_class_name(name: str) -> bool:
    """Query/filter input and partial-update DTO names are all-optional by design."""
    return name.endswith(DTO_CLASS_NAME_SUFFIXES) or name.startswith(DTO_CLASS_NAME_PREFIXES)


def _is_single_value_literal(node: ast.AST | None) -> bool:
    """Detect a single-constant `Literal[X]` annotation.

    A one-element `Literal` (e.g. `type: Literal["complete"]`) is the canonical
    tag of a discriminated-union arm, so a model carrying one is already modelled
    correctly. A multi-value `Literal[...]` is still a poor-man's discriminator.
    """
    if node is None:
        return False
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            parsed = ast.parse(node.value, mode="eval")
        except SyntaxError:
            return False
        return _is_single_value_literal(parsed.body)
    if not isinstance(node, ast.Subscript):
        return False
    if _get_name_flat(node.value).rsplit(".", 1)[-1] != "Literal":
        return False
    slice_node = node.slice
    if type(slice_node).__name__ == "Index":
        slice_node = getattr(slice_node, "value", slice_node)
    if isinstance(slice_node, ast.Tuple):
        return len(slice_node.elts) == 1
    return True


def _inherits_basemodel(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "BaseModel":
            return True
        if isinstance(base, ast.Attribute) and base.attr == "BaseModel":
            return True
    return False


def _is_dataclass(node: ast.ClassDef) -> bool:
    """Detect `@dataclass`, `@dataclasses.dataclass`, and called forms."""
    for deco in node.decorator_list:
        target = deco.func if isinstance(deco, ast.Call) else deco
        name = _get_name_flat(target)
        if name == "dataclass" or name.endswith(".dataclass"):
            return True
    return False


def _collect_str_enum_names(tree: ast.Module) -> set[str]:
    """Names of classes in this module that look like string enums.

    Matches `class X(StrEnum)`, `class X(enum.StrEnum)`, and the
    pre-3.11 `class X(str, Enum)` spelling.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        base_names = {_get_name_flat(base).rsplit(".", 1)[-1] for base in node.bases}
        if "StrEnum" in base_names or {"str", "Enum"} <= base_names:
            names.add(node.name)
    return names


def _is_bool_tuple(node: ast.AST | None) -> bool:
    """Detect a two-element `tuple[bool, X]` / `tuple[X, bool]` annotation."""
    if node is None:
        return False
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            parsed = ast.parse(node.value, mode="eval")
        except SyntaxError:
            return False
        return _is_bool_tuple(parsed.body)
    if not isinstance(node, ast.Subscript):
        return False
    name = _get_name_flat(node.value).rsplit(".", 1)[-1]
    if name not in {"tuple", "Tuple"}:
        return False
    slice_node = node.slice
    # Handle Python < 3.9 Index wrapper safely
    if type(slice_node).__name__ == "Index":
        slice_node = getattr(slice_node, "value", slice_node)
    if not isinstance(slice_node, ast.Tuple) or len(slice_node.elts) != 2:
        return False
    elts = slice_node.elts
    # `tuple[bool, ...]` is a homogeneous variadic tuple, not an (ok, value) pair.
    if any(isinstance(e, ast.Constant) and e.value is Ellipsis for e in elts):
        return False
    return any(_is_bool(e) for e in elts)


def _is_bool(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "bool"
    if isinstance(node, ast.Attribute):
        return node.attr == "bool"
    return False


def _is_discriminator_type(node: ast.AST | None, str_enum_names: set[str]) -> bool:
    """Detect a str / StrEnum / Literal annotation (optionally unioned with None)."""
    if node is None:
        return False
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            parsed = ast.parse(node.value, mode="eval")
        except SyntaxError:
            return False
        return _is_discriminator_type(parsed.body, str_enum_names)
    if isinstance(node, ast.Name):
        return node.id == "str" or node.id in str_enum_names
    if isinstance(node, ast.Attribute):
        return node.attr in str_enum_names
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _is_discriminator_type(node.left, str_enum_names) or _is_discriminator_type(
            node.right, str_enum_names
        )
    if isinstance(node, ast.Subscript):
        name = _get_name_flat(node.value).rsplit(".", 1)[-1]
        if name == "Literal":
            return True
        if name == "Optional":
            return _is_discriminator_type(node.slice, str_enum_names)
    return False


def _get_name_flat(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        val = _get_name_flat(node.value)
        if val:
            return f"{val}.{node.attr}"
    return ""


def _is_optional(node: ast.AST | None) -> bool:
    """Detect if an annotation represents an Optional type or Union with None."""
    if node is None:
        return False

    # If it's a string literal (forward ref), parse it and check the inner AST
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            parsed = ast.parse(node.value, mode="eval")
            return _is_optional(parsed.body)
        except SyntaxError:
            pass

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _is_optional(node.left) or _is_optional(node.right)

    if isinstance(node, ast.Subscript):
        name = _get_name_flat(node.value)
        if name == "Optional" or name.endswith(".Optional"):
            return True
        if name == "Union" or name.endswith(".Union"):
            slice_node = node.slice
            # Handle Python < 3.9 Index wrapper safely
            if type(slice_node).__name__ == "Index":
                slice_node = getattr(slice_node, "value", slice_node)
            if isinstance(slice_node, ast.Tuple):
                return any(_is_optional(elt) for elt in slice_node.elts)
            return _is_optional(slice_node)

    if isinstance(node, ast.Constant) and node.value is None:
        return True

    if isinstance(node, ast.Name) and node.id == "None":
        return True

    return False
