"""SARJ001: detect the `for x in xs: await f(x)` gather antipattern.

Sequential `await` in a for-loop serializes I/O that could be parallelized
with `asyncio.gather([f(x) for x in xs])`. The performance gap is often 10-100x
for network-bound work (HTTP, DB queries, LLM calls).

Deliberately narrow, to flag the textbook antipattern and almost nothing else —
an over-broad version drowned real signal under suppressions. The rule fires
only for:

* a `for` loop whose body is **straight-line** (no `if`/`try`/`with`/`return`/
  `break`/`continue`/`raise`/nested loop — those signal conditional or ordered
  logic, not a parallel map) and awaits a call that **uses the loop variable**
  (so each iteration is a distinct, independent call); or
* a comprehension / generator expression with an `await` in its element or a
  per-element `if` (those have no ordered side effects).

It does NOT fire for: `while` loops (pagination, polling, queue drains — length
unknown, inherently sequential), a loop's once-evaluated iterable
(`for x in await fetch()`), `async for`, test modules (intentional ordering),
or a `for` body containing control flow. Those were the false-positive sources.

References:
- https://docs.python.org/3/library/asyncio-task.html#running-tasks-concurrently
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule


if TYPE_CHECKING:
    from pathlib import Path


def _is_test_path(path: Path) -> bool:
    name = path.name
    if name == "conftest.py" or name.startswith("test_") or name.endswith("_test.py"):
        return True
    return any(part in {"tests", "test"} for part in path.parts)


class NoSequentialAwait(Rule):
    """Sequential await calls in a loop that could be parallelized."""

    id: str = "no-sequential-await"
    code: str = "SARJ001"
    description: str = "Sequential `await` in a for-loop — prefer asyncio.gather."

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        if _is_test_path(path):
            return []
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return []
        visitor = _SequentialAwaitVisitor()
        visitor.visit(tree)
        diags = [
            Diagnostic(
                path=path,
                line=node.lineno,
                col=node.col_offset + 1,
                code=self.code,
                message=("Sequential `await` inside `for` — prefer `asyncio.gather([f(x) for x in xs])`."),
            )
            for node in visitor.hits
        ]
        diags.sort(key=lambda d: (d.line, d.col))
        return diags


# A loop's *iterable* is evaluated once in the enclosing scope, NOT per element:
# `for x in await fetch()` / `{x for x in await fetch()}` await once. Iterables
# are visited *before* the loop is pushed, so an await there attributes to an
# enclosing loop (if any), not this one.
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)

# Top-level body statements that signal conditional or ordered logic rather than
# a straight-line parallel map. A `for` whose body contains any of these is not
# treated as the gather antipattern.
_CONTROL_FLOW = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.Match,
    ast.Return,
    ast.Break,
    ast.Continue,
    ast.Raise,
)


def _names(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _is_gather_antipattern(node: ast.For) -> bool:
    """True for `for x in xs: <straight-line body awaiting a call that uses x>`."""
    if any(isinstance(stmt, _CONTROL_FLOW) for stmt in node.body):
        return False
    targets = _names(node.target)
    for stmt in node.body:
        for inner in ast.walk(stmt):
            if isinstance(inner, ast.Await) and _names(inner) & targets:
                return True
    return False


class _SequentialAwaitVisitor(ast.NodeVisitor):
    """Single O(n) pass: flag the first per-iteration `await` of each loop.

    Maintains a stack of enclosing loops within the current function. The stack
    resets at function boundaries so a loop in an outer function never claims an
    `await` in a nested one. Each loop is flagged at most once. A loop's
    once-evaluated iterable is excluded (see module comment).
    """

    def __init__(self) -> None:
        super().__init__()
        self._loops: list[ast.AST] = []
        self._flagged: set[int] = set()
        self.hits: list[ast.Await] = []

    def _flag_if_in_loop(self, node: ast.Await) -> None:
        if self._loops:
            loop = self._loops[-1]
            if id(loop) not in self._flagged:
                self._flagged.add(id(loop))
                self.hits.append(node)

    def visit_For(self, node: ast.For) -> None:
        # `<iter>` runs once in the enclosing scope; visit it before entering.
        self.visit(node.iter)
        # Only a straight-line per-element-await body is the gather antipattern;
        # control-flow bodies (conditional/ordered) are not pushed, so awaits in
        # them are not flagged for this loop.
        antipattern = _is_gather_antipattern(node)
        if antipattern:
            self._loops.append(node)
        self.visit(node.target)
        for stmt in (*node.body, *node.orelse):
            self.visit(stmt)
        if antipattern:
            self._loops.pop()

    def _visit_comprehension(self, node: ast.AST, elements: tuple[ast.expr, ...]) -> None:
        gens: list[ast.comprehension] = node.generators  # pyright: ignore[reportAttributeAccessIssue]
        # Outermost iterable is evaluated once in the enclosing scope.
        self.visit(gens[0].iter)
        self._loops.append(node)
        for elt in elements:
            self.visit(elt)
        self.visit(gens[0].target)
        for cond in gens[0].ifs:
            self.visit(cond)
        # Later generators iterate per element of the preceding one.
        for gen in gens[1:]:
            self.visit(gen.iter)
            self.visit(gen.target)
            for cond in gen.ifs:
                self.visit(cond)
        self._loops.pop()

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension(node, (node.elt,))

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension(node, (node.elt,))

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension(node, (node.elt,))

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension(node, (node.key, node.value))

    @override
    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(node, _SCOPES):
            saved = self._loops
            self._loops = []
            super().generic_visit(node)
            self._loops = saved
        elif isinstance(node, ast.Await):
            self._flag_if_in_loop(node)
            super().generic_visit(node)
        else:
            super().generic_visit(node)
