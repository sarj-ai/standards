"""SARJ023: stepdown rule — a single-caller private helper belongs below its caller.

A file should read top-to-bottom like a newspaper: public API first, then the
private helpers it uses. This rule encodes only the fully unambiguous core of
that convention.

The rule is deliberately restricted to helpers with EXACTLY ONE same-scope
caller. For a single-caller helper there is one canonical stepdown position —
immediately below its sole caller — so a violation ("helper sits above its only
caller") has a single, non-arbitrary fix and the reorder is a clear readability
win. Helpers with two or more callers are OUT OF SCOPE: a shared helper has no
canonical "below which caller?" answer (stepping below one caller reads wrong
relative to the others), and the verdict would flip whenever a caller moves.
That multi-caller arbitrariness is exactly the disputed-churn class this
redesign removes.

Fires on:
1. **Module-level helper above its one caller** — a private top-level function
   (`_name`) referenced at call time by EXACTLY ONE top-level function/class,
   and defined above that caller.
2. **Class-level private method above its one caller** — a private, non-dunder
   method referenced via `self._name` / `cls._name` by EXACTLY ONE sibling
   method, and defined above it.

Never fires on:
- Public defs and private top-level classes (declarations, not helpers).
- Unused helpers (no same-scope caller).
- Helpers with two or more same-scope callers (no canonical stepdown target).
- Mutual / indirect / two-node recursion — cycles have no valid stepdown order.
- Names that are position-pinned by an import-time / class-creation-time
  reference: module-level statements, decorator lists, default arguments,
  annotations, class-body attribute values. Moving those breaks runtime.
- Names referenced inside `if TYPE_CHECKING:` blocks (pinned, not call sites).
- Names defined more than once in the scope (`@overload`, `@x.setter`,
  conditional defs), reassigned at module/class scope, or locally rebound
  inside the calling function itself — the reference there resolves to the
  local, so that function is not counted as a caller. A local binding in some
  OTHER (non-calling) function does not suppress the helper.
- Methods decorated `@property` / `@cached_property` (read as attributes) and
  `@abstractmethod` (interface contracts conventionally sit together).
"""

from __future__ import annotations

import ast
from collections import Counter
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule, parse_or_none


if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from pathlib import Path


_DEF_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)
_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

#: Decorator names that exempt a method from being flagged: property-like
#: methods read as attributes, and abstract methods are interface declarations.
_EXEMPT_METHOD_DECORATORS = frozenset({"property", "cached_property", "abstractmethod", "setter", "getter", "deleter"})

_SELF_NAMES = frozenset({"self", "cls"})


def _child_nodes(node: ast.AST) -> Iterator[ast.AST]:
    for field in node._fields:
        val = getattr(node, field, None)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, ast.AST):
                    yield item
        elif isinstance(val, ast.AST):
            yield val


def _walk(node: ast.AST) -> Iterator[ast.AST]:
    stack: list[ast.AST] = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(_child_nodes(n))


class Stepdown(Rule):
    """Single-caller private helper defined above its only caller — move it below."""

    id: str = "stepdown"
    code: str = "SARJ023"
    description: str = "Private helper defined above its only caller — move it below the code that calls it."

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        if _is_test_path(path):
            return []
        tree = parse_or_none(path, source)
        if tree is None:
            return []
        diags = _check_module_scope(path, tree, self.code)
        for node in _walk(tree):
            if isinstance(node, ast.ClassDef):
                diags.extend(_check_class_scope(path, node, self.code))
        diags.sort(key=lambda d: (d.line, d.col))
        return diags


def _check_module_scope(path: Path, tree: ast.Module, code: str) -> list[Diagnostic]:
    defs = [n for n in tree.body if isinstance(n, _SCOPE_NODES)]
    counts = Counter(d.name for d in defs)
    unique_defs = {d.name: d for d in defs if counts[d.name] == 1}

    pinned = _module_pinned_names(tree)
    shadowed = _module_assigned_names(tree)

    graph: dict[str, set[str]] = {}
    for name, d in unique_defs.items():
        refs = {
            n.id for n in _runtime_nodes(_deferred_body(d)) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
        }
        graph[name] = (refs & unique_defs.keys()) - {name} - _locally_bound_names(d)

    diags: list[Diagnostic] = []
    for name, d in unique_defs.items():
        if not isinstance(d, _DEF_NODES) or not _is_private_helper_name(name):
            continue
        if name in pinned or name in shadowed:
            continue
        diags.extend(_flag_if_above_single_caller(path, code, name, node=d, graph=graph, defs=unique_defs))
    return diags


def _check_class_scope(path: Path, cls: ast.ClassDef, code: str) -> list[Diagnostic]:
    methods = [n for n in cls.body if isinstance(n, _DEF_NODES)]
    counts = Counter(m.name for m in methods)
    unique = {m.name: m for m in methods if counts[m.name] == 1}

    pinned = _class_pinned_names(cls)
    shadowed = _class_attr_names(cls)
    for m in methods:
        shadowed |= _self_attribute_stores(m)

    graph: dict[str, set[str]] = {}
    for name, m in unique.items():
        refs = {
            n.attr
            for n in _runtime_nodes(m.body)
            if isinstance(n, ast.Attribute)
            and isinstance(n.ctx, ast.Load)
            and isinstance(n.value, ast.Name)
            and (n.value.id in _SELF_NAMES or n.value.id == cls.name)
        }
        graph[name] = (refs & unique.keys()) - {name}

    diags: list[Diagnostic] = []
    for name, m in unique.items():
        if not _is_private_helper_name(name):
            continue
        if name in pinned or name in shadowed or _has_exempt_decorator(m):
            continue
        diags.extend(_flag_if_above_single_caller(path, code, name, node=m, graph=graph, defs=unique))
    return diags


def _flag_if_above_single_caller(
    path: Path,
    code: str,
    name: str,
    *,
    node: ast.stmt,
    graph: dict[str, set[str]],
    defs: Mapping[str, ast.stmt],
) -> list[Diagnostic]:
    callers = [c for c, callees in graph.items() if name in callees]
    if len(callers) != 1:
        return []
    (caller,) = callers
    if _reaches(graph, name, caller):
        return []
    if node.lineno >= defs[caller].lineno:
        return []
    return [
        Diagnostic(
            path=path,
            line=node.lineno,
            col=node.col_offset + 1,
            code=code,
            message=(
                f"private helper `{name}` is defined above its only caller "
                f"`{caller}` (line {defs[caller].lineno}) — "
                "move it directly below the code that calls it (stepdown rule)."
            ),
        )
    ]


def _is_private_helper_name(name: str) -> bool:
    if not name.startswith("_"):
        return False
    return not (name.startswith("__") and name.endswith("__"))


def _has_exempt_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        match target:
            case ast.Name(id=name) if name in _EXEMPT_METHOD_DECORATORS:
                return True
            case ast.Attribute(attr=attr) if attr in _EXEMPT_METHOD_DECORATORS:
                return True
            case _:
                pass
    return False


def _deferred_body(node: ast.stmt) -> list[ast.stmt]:
    """Statements that execute only when the def is invoked, not at import.

    For a function that is its body; for a class it is the bodies of its
    (recursively nested) methods — class-body statements run at class-creation
    time and are handled as pinning references instead.
    """
    if isinstance(node, _DEF_NODES):
        return node.body
    if isinstance(node, ast.ClassDef):
        return [
            stmt
            for child in node.body
            if isinstance(child, (*_DEF_NODES, ast.ClassDef))
            for stmt in _deferred_body(child)
        ]
    return []


def _runtime_nodes(stmts: list[ast.stmt]) -> Iterator[ast.expr]:
    """Yield expression nodes reachable at call time within `stmts`.

    Skips decorator lists / defaults / annotations of the given defs' nested
    defs only where they run at definition time relative to the enclosing
    scope; inside an already-deferred body, nested decorators and defaults DO
    run at call time and are included. Annotations and `if TYPE_CHECKING:`
    bodies are never included.
    """
    stack: list[ast.AST] = list(stmts)
    while stack:
        node = stack.pop()
        match node:
            case ast.FunctionDef() | ast.AsyncFunctionDef():
                stack.extend(node.body)
                stack.extend(node.decorator_list)
                stack.extend(node.args.defaults)
                stack.extend(d for d in node.args.kw_defaults if d is not None)
            case ast.ClassDef():
                stack.extend(node.body)
                stack.extend(node.decorator_list)
                stack.extend(node.bases)
                stack.extend(k.value for k in node.keywords)
            case ast.AnnAssign():
                if node.value is not None:
                    stack.append(node.value)
            case ast.If() if _is_type_checking_test(node.test):
                stack.extend(node.orelse)
            case ast.expr():
                yield node
                stack.extend(_child_nodes(node))
            case _:
                stack.extend(_child_nodes(node))


def _module_pinned_names(tree: ast.Module) -> set[str]:
    pinned: set[str] = set()
    for stmt in tree.body:
        if isinstance(stmt, _DEF_NODES):
            pinned |= _immediate_def_refs(stmt)
        elif isinstance(stmt, ast.ClassDef):
            pinned |= _class_pinned_names(stmt) | _immediate_class_header_refs(stmt)
        else:
            pinned |= _name_loads(stmt)
    return pinned


def _class_pinned_names(cls: ast.ClassDef) -> set[str]:
    """Bare names referenced at class-creation time inside the class body."""
    pinned: set[str] = set()
    for stmt in cls.body:
        if isinstance(stmt, _DEF_NODES):
            pinned |= _immediate_def_refs(stmt)
        elif isinstance(stmt, ast.ClassDef):
            pinned |= _class_pinned_names(stmt) | _immediate_class_header_refs(stmt)
        else:
            pinned |= _name_loads(stmt)
    return pinned


def _immediate_def_refs(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Names evaluated at `def` time: decorators, defaults, annotations."""
    parts: list[ast.expr] = list(node.decorator_list)
    parts.extend(node.args.defaults)
    parts.extend(d for d in node.args.kw_defaults if d is not None)
    args = node.args
    parts.extend(
        a.annotation
        for a in (*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg)
        if a is not None and a.annotation is not None
    )
    if node.returns is not None:
        parts.append(node.returns)
    out: set[str] = set()
    for p in parts:
        out |= _name_loads(p)
    return out


def _immediate_class_header_refs(cls: ast.ClassDef) -> set[str]:
    out: set[str] = set()
    for p in (*cls.decorator_list, *cls.bases, *(k.value for k in cls.keywords)):
        out |= _name_loads(p)
    return out


def _name_loads(node: ast.AST) -> set[str]:
    """Load-context bare names evaluated where `node` sits at import/def time.

    A lambda body is deferred — it runs only when the lambda is later invoked,
    not at the point the lambda literal is created — so names inside it are not
    import-time pins. Lambda argument defaults DO evaluate at creation time and
    are kept.
    """
    out: set[str] = set()
    stack: list[ast.AST] = [node]
    while stack:
        n = stack.pop()
        if isinstance(n, ast.Lambda):
            stack.extend(n.args.defaults)
            stack.extend(d for d in n.args.kw_defaults if d is not None)
            continue
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            out.add(n.id)
        stack.extend(_child_nodes(n))
    return out


def _module_assigned_names(tree: ast.Module) -> set[str]:
    out: set[str] = set()
    for stmt in tree.body:
        if isinstance(stmt, _SCOPE_NODES):
            continue
        for n in _walk(stmt):
            if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                out.add(n.id)
            elif isinstance(n, ast.alias):
                out.add((n.asname or n.name).split(".")[0])
    return out


def _class_attr_names(cls: ast.ClassDef) -> set[str]:
    out: set[str] = set()
    for stmt in cls.body:
        if isinstance(stmt, _SCOPE_NODES):
            continue
        for n in _walk(stmt):
            if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                out.add(n.id)
    return out


def _self_attribute_stores(node: ast.stmt) -> set[str]:
    return {
        n.attr
        for n in _walk(node)
        if isinstance(n, ast.Attribute)
        and isinstance(n.ctx, (ast.Store, ast.Del))
        and isinstance(n.value, ast.Name)
        and n.value.id in _SELF_NAMES
    }


def _locally_bound_names(node: ast.stmt) -> set[str]:
    comp_targets = {
        id(t)
        for n in _walk(node)
        if isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp))
        for gen in n.generators
        for t in _walk(gen.target)
        if isinstance(t, ast.Name)
    }
    bound: set[str] = set()
    for n in _walk(node):
        match n:
            case ast.Name(ctx=ast.Store() | ast.Del()) if id(n) not in comp_targets:
                bound.add(n.id)
            case ast.arg():
                bound.add(n.arg)
            case ast.FunctionDef() | ast.AsyncFunctionDef() | ast.ClassDef() if n is not node:
                bound.add(n.name)
            case ast.alias():
                bound.add((n.asname or n.name).split(".")[0])
            case ast.MatchAs(name=str() as nm) | ast.MatchStar(name=str() as nm):
                bound.add(nm)
            case ast.MatchMapping(rest=str() as nm):
                bound.add(nm)
            case _:
                pass
    return bound


def _is_type_checking_test(test: ast.expr) -> bool:
    match test:
        case ast.Name(id="TYPE_CHECKING"):
            return True
        case ast.Attribute(attr="TYPE_CHECKING"):
            return True
        case _:
            return False


def _reaches(graph: dict[str, set[str]], start: str, target: str) -> bool:
    seen: set[str] = set()
    stack = [start]
    while stack:
        node = stack.pop()
        for nxt in graph.get(node, ()):
            if nxt == target:
                return True
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return False


def _is_test_path(path: Path) -> bool:
    if path.name == "conftest.py":
        return True
    if path.name.startswith("test_"):
        return True
    return "tests" in path.parts
