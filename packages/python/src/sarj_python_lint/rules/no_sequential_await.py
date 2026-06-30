"""SARJ001: detect `for x in xs: await f(x)` patterns.

Sequential `await` in a for-loop serializes I/O that could be parallelized
with `asyncio.gather([f(x) for x in xs])`. The performance gap is often 10-100x
for network-bound work (HTTP, DB queries, LLM calls).

Test modules are exempt: sequential awaits in tests are overwhelmingly
intentional ordering (seeding rows so `created_at` stays strictly increasing,
step-by-step assertions, per-item isolation). `asyncio.gather` would race that
ordering, and the parallelism payoff does not apply to test setup — so the rule
fired almost exclusively as a false positive there.

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


# `while` and the comprehension element/condition run once per iteration, so a
# bare `await` there serializes the loop. `async for` is deliberately absent — it
# is the parallel-iteration construct, not the antipattern.
#
# A loop's *iterable* is the exception: in `for x in <iter>` (and a
# comprehension's outermost `for ... in <iter>`), `<iter>` is evaluated exactly
# once in the enclosing scope, NOT per element. So `for x in await fetch()` and
# `{x for x in await fetch()}` await once and must not be flagged — that was a
# false positive that forced suppressions across real code. Those iterables are
# visited *before* the loop is pushed, so any await in them attributes to an
# enclosing loop (if one exists) rather than to this one.
_WHILE = (ast.While,)
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


class _SequentialAwaitVisitor(ast.NodeVisitor):
    """Single O(n) pass: flag the first per-iteration `await` of each loop.

    Maintains a stack of enclosing loops within the current function. The stack
    resets at function boundaries so a loop in an outer function never claims an
    `await` in a nested one. Each loop is flagged at most once. A loop's
    once-evaluated iterable is excluded (see module comment).
    """

    def __init__(self) -> None:
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
        self._loops.append(node)
        self.visit(node.target)
        for stmt in (*node.body, *node.orelse):
            self.visit(stmt)
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
        elif isinstance(node, _WHILE):
            self._loops.append(node)
            super().generic_visit(node)
            self._loops.pop()
        elif isinstance(node, ast.Await):
            self._flag_if_in_loop(node)
            super().generic_visit(node)
        else:
            super().generic_visit(node)
