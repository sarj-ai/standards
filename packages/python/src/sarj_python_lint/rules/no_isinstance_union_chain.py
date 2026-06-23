"""SARJ003: flag `if/elif isinstance(...)` chains that dispatch over a closed union.

A chain of `if isinstance(x, A): ... elif isinstance(x, B): ...` (2+ branches, same
target, each branch testing one locally-defined class) is almost always dispatch over a
closed discriminated union. `match`/`case` with `assert_never` in the fallthrough is
strictly better: pyright reports an error the moment a new variant is added and a branch
is missed — a plain `isinstance` chain silently falls through.

    # flagged
    if isinstance(subject, ApiKeySubject):
        ...
    elif isinstance(subject, JwtSubject):
        ...

    # preferred
    match subject:
        case ApiKeySubject():
            ...
        case JwtSubject():
            ...
        case _:
            assert_never(subject)

This is a heuristic, not a proof the union is closed — so it accepts some false positives.
Suppress a deliberate boundary chain with `# sarj-noqa: SARJ003 — <reason>`.

Deliberately NOT flagged (boundary/runtime checks, not closed-union dispatch):
- a single `isinstance` guard (no chain),
- `isinstance(x, (A, B))` tuple-membership (one check, not a dispatch chain),
- any chain whose branches test builtins/stdlib types (`dict`, `str`, `list`, `Exception`,
  `datetime`, ...), the generated-SDK `Unset` sentinel, or `collections.abc`/`typing` ABCs,
- any chain mixing `isinstance` with a non-`isinstance` condition (e.g. `hasattr`, a
  comparison, a boolean combination) — a defensive guard, not a clean dispatch.

References:
- https://docs.python.org/3/library/typing.html#typing.assert_never
- https://typing.python.org/en/latest/spec/narrowing.html#assert-never-and-exhaustiveness-checking
"""

from __future__ import annotations

import ast
from pathlib import Path

from sarj_python_lint.rule_base import Diagnostic, Rule

_EXCLUDED_TYPE_NAMES = frozenset(
    {
        "dict",
        "str",
        "list",
        "tuple",
        "set",
        "frozenset",
        "int",
        "float",
        "bool",
        "complex",
        "bytes",
        "bytearray",
        "type",
        "object",
        "Exception",
        "BaseException",
        "NoneType",
        "Unset",
        "datetime",
        "date",
        "time",
        "timedelta",
        "Mapping",
        "MutableMapping",
        "Sequence",
        "MutableSequence",
        "Iterable",
        "Iterator",
        "Collection",
        "Container",
        "Set",
        "Hashable",
        "Callable",
    }
)


class NoIsinstanceUnionChain(Rule):
    """`if/elif isinstance` chains over local classes — prefer match/case + assert_never."""

    id = "no-isinstance-union-chain"
    code = "SARJ003"
    description = (
        "if/elif isinstance chain over local classes — prefer match/case with "
        "assert_never for compile-time exhaustiveness."
    )

    def check(self, path: Path, source: str) -> list[Diagnostic]:
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return []
        elif_nodes = _collect_elif_nodes(tree)
        diags: list[Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.If) or id(node) in elif_nodes:
                continue
            count = _qualifying_chain_length(node)
            if count >= 2:
                diags.append(
                    Diagnostic(
                        path=path,
                        line=node.lineno,
                        col=node.col_offset + 1,
                        code=self.code,
                        message=(
                            f"if/elif isinstance chain over {count} types — prefer "
                            "match/case with assert_never for exhaustiveness."
                        ),
                    )
                )
        return diags


def _collect_elif_nodes(tree: ast.AST) -> set[int]:
    """ids of `If` nodes that are the sole `orelse` of another `If` (i.e. `elif` arms)."""
    elifs: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
            elifs.add(id(node.orelse[0]))
    return elifs


def _qualifying_chain_length(head: ast.If) -> int:
    """Number of branches if `head` is an all-`isinstance`-on-one-target chain, else 0.

    Returns 0 if any branch is not `isinstance(<same target>, <single local class>)`.
    """
    target_dump: str | None = None
    count = 0
    current: ast.If | None = head
    while current is not None:
        type_arg = _isinstance_single_type(current.test)
        if type_arg is None:
            return 0
        target, type_name = type_arg
        if type_name in _EXCLUDED_TYPE_NAMES:
            return 0
        dumped = ast.dump(target)
        if target_dump is None:
            target_dump = dumped
        elif dumped != target_dump:
            return 0
        count += 1
        if len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
            current = current.orelse[0]
        else:
            current = None
    return count


def _isinstance_single_type(test: ast.expr) -> tuple[ast.expr, str] | None:
    """If `test` is `isinstance(x, SomeClass)` with a single Name/Attribute class, return
    (target, class_name); else None. Tuple-form `isinstance(x, (A, B))` returns None."""
    if not isinstance(test, ast.Call):
        return None
    if not (isinstance(test.func, ast.Name) and test.func.id == "isinstance"):
        return None
    if len(test.args) != 2 or test.keywords:
        return None
    target, type_node = test.args
    name = _class_name(type_node)
    if name is None:
        return None
    return target, name


def _class_name(node: ast.expr) -> str | None:
    """The trailing name of a class reference: `Foo` / `mod.Foo` -> 'Foo'. None for tuples
    or anything that isn't a plain Name/Attribute (e.g. a subscript or tuple-membership)."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None
