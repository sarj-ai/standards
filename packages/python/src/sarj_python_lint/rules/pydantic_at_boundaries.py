"""SARJ008: untyped dict / heterogeneous tuple at a function boundary — use pydantic.

The anti-pattern:

    def build_payload(call: Call) -> dict[str, Any]:
        return {"id": call.id, "status": call.status}

    async def stop_call(...) -> tuple[bool, str | None]:
        ...

    @router.get("/calls/{call_id}")
    async def get_call(call_id: str):   # no return annotation at all
        ...

Raw ``dict[str, Any]`` / ``dict[str, object]`` / bare ``dict`` returns and
heterogeneous ``tuple[...]`` returns hide the shape of the data from both the
type checker and the reader. Define a pydantic model (or frozen dataclass)
instead — Python analogue of ``@sarj/prefer-schema-for-api-payload``:

    class CallPayload(BaseModel):
        id: CallId
        status: CallStatus

    def build_payload(call: Call) -> CallPayload: ...

Purely annotation-based (no type inference), checked on function definitions
(sync + async):

1. Return annotation that is ``dict[str, Any]`` / ``dict[str, object]`` /
   bare ``dict`` / ``Dict``, ``list[dict[str, Any]]``, or a ``tuple[...]``
   with 2+ distinct element types.
2. FastAPI route handlers (``@router.get(...)`` / ``@app.post(...)`` etc.)
   with no return annotation and no ``response_model=`` in the decorator.

Not flagged: fully-concrete dict value types (``dict[str, str]``),
homogeneous tuples (``tuple[int, ...]``, ``tuple[str, str]``), heterogeneous
tuple returns from private (``_``-prefixed) non-route functions, ``@overload``
stubs, and test files.

References:
- https://docs.pydantic.dev/latest/concepts/models/
- https://fastapi.tiangolo.com/tutorial/response-model/
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from sarj_python_lint.rule_base import Diagnostic, Rule

_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
_DICT_NAMES = {"dict", "Dict"}
_LIST_NAMES = {"list", "List"}
_TUPLE_NAMES = {"tuple", "Tuple"}
_ANY_VALUE_NAMES = {"Any", "object"}


@dataclass(frozen=True, slots=True)
class _RouteInfo:
    """A FastAPI route decorator found on a function."""

    has_response_model: bool


class PydanticAtBoundaries(Rule):
    """Untyped dict / heterogeneous tuple return — define a pydantic model."""

    id = "pydantic-at-boundaries"
    code = "SARJ008"
    description = (
        "Function returns an untyped dict or heterogeneous tuple — "
        "define a pydantic model (or frozen dataclass)."
    )

    def check(self, path: Path, source: str) -> list[Diagnostic]:
        if _is_test_path(path):
            return []
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return []
        diags: list[Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if _is_overload(node):
                continue
            route = _route_info(node)
            returns = _resolve_annotation(node.returns)
            if returns is None:
                if route is not None and not route.has_response_model:
                    diags.append(
                        Diagnostic(
                            path=path,
                            line=node.lineno,
                            col=node.col_offset + 1,
                            code=self.code,
                            message=(
                                f"FastAPI route `{node.name}` has no return "
                                "annotation — declare a pydantic response model "
                                "(or pass `response_model=`)."
                            ),
                        )
                    )
                continue
            kind = _classify_return(returns)
            if kind is None:
                continue
            # Private functions returning heterogeneous tuples are common and
            # fine-ish; untyped dicts are flagged everywhere.
            if kind == "tuple" and route is None and node.name.startswith("_"):
                continue
            ann_text = ast.unparse(returns)
            diags.append(
                Diagnostic(
                    path=path,
                    line=node.lineno,
                    col=node.col_offset + 1,
                    code=self.code,
                    message=(
                        f"`{node.name}` returns `{ann_text}` — define a "
                        "pydantic model (or frozen dataclass) for this shape."
                    ),
                )
            )
        return diags


def _is_test_path(path: Path) -> bool:
    return path.name.startswith("test_") or "tests" in path.parts


def _is_overload(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == "overload":
            return True
        if isinstance(dec, ast.Attribute) and dec.attr == "overload":
            return True
    return False


def _route_info(node: ast.FunctionDef | ast.AsyncFunctionDef) -> _RouteInfo | None:
    """Detect a FastAPI route decorator: `@<router|app|*_router>.<method>(...)`."""
    for dec in node.decorator_list:
        if not isinstance(dec, ast.Call):
            continue
        func = dec.func
        if not isinstance(func, ast.Attribute) or func.attr not in _HTTP_METHODS:
            continue
        receiver = func.value
        if not isinstance(receiver, ast.Name):
            continue
        name = receiver.id
        if name in {"app", "router"} or name.endswith("_router"):
            has_response_model = any(kw.arg == "response_model" for kw in dec.keywords)
            return _RouteInfo(has_response_model=has_response_model)
    return None


def _resolve_annotation(node: ast.expr | None) -> ast.expr | None:
    """Unwrap a string forward-reference annotation into its parsed expression."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            return ast.parse(node.value, mode="eval").body
        except SyntaxError:
            return None
    return node


def _classify_return(node: ast.expr) -> str | None:
    """Return "dict" / "tuple" if the annotation is a flagged shape, else None."""
    # Look through `X | None` / Optional[X] / Union[...] members.
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _classify_return(node.left) or _classify_return(node.right)

    name = _flat_name(node)
    if name in _DICT_NAMES:
        return "dict"  # bare `dict` / `Dict`

    if not isinstance(node, ast.Subscript):
        return None

    base = _flat_name(node.value)
    if base == "Optional":
        return _classify_return(node.slice)
    if base == "Union":
        if isinstance(node.slice, ast.Tuple):
            for elt in node.slice.elts:
                kind = _classify_return(elt)
                if kind is not None:
                    return kind
            return None
        return _classify_return(node.slice)
    if base in _LIST_NAMES:
        # Only list-of-untyped-dict is flagged (e.g. `list[dict[str, Any]]`).
        inner = _classify_return(node.slice)
        return "dict" if inner == "dict" else None
    if base in _DICT_NAMES:
        return "dict" if _is_untyped_dict_args(node.slice) else None
    if base in _TUPLE_NAMES:
        return "tuple" if _is_heterogeneous_tuple_args(node.slice) else None
    return None


def _is_untyped_dict_args(slice_node: ast.expr) -> bool:
    """`dict[K, V]` is flagged only when V is `Any` or `object`."""
    if not isinstance(slice_node, ast.Tuple) or len(slice_node.elts) != 2:
        return False
    return _flat_name(slice_node.elts[1]) in _ANY_VALUE_NAMES


def _is_heterogeneous_tuple_args(slice_node: ast.expr) -> bool:
    """`tuple[...]` is flagged when it has 2+ distinct element types."""
    if not isinstance(slice_node, ast.Tuple):
        return False  # single-element `tuple[X]`
    # `tuple[X, ...]` is a homogeneous variadic tuple.
    if any(isinstance(elt, ast.Constant) and elt.value is Ellipsis for elt in slice_node.elts):
        return False
    distinct = {ast.unparse(elt) for elt in slice_node.elts}
    return len(distinct) >= 2


def _flat_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr  # `typing.Dict` -> `Dict`
    return ""
