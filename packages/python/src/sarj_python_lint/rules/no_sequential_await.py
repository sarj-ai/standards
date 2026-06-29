"""SARJ001: detect `for x in xs: await f(x)` patterns.

Sequential `await` in a for-loop serializes I/O that could be parallelized
with `asyncio.gather([f(x) for x in xs])`. The performance gap is often 10-100x
for network-bound work (HTTP, DB queries, LLM calls).

References:
- https://docs.python.org/3/library/asyncio-task.html#running-tasks-concurrently
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule


if TYPE_CHECKING:
    from pathlib import Path


class NoSequentialAwait(Rule):
    """Sequential await calls in a loop that could be parallelized."""

    id: str = "no-sequential-await"
    code: str = "SARJ001"
    description: str = "Sequential `await` in a for-loop — prefer asyncio.gather."

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
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
                message=(
                    "Sequential `await` inside `for` — prefer "
                    "`asyncio.gather([f(x) for x in xs])`."
                ),
            )
            for node in visitor.hits
        ]
        diags.sort(key=lambda d: (d.line, d.col))
        return diags


# Loop-like constructs whose body runs once per element: `await` inside one of
# them serializes the iterations. `async for` is deliberately absent — it is the
# parallel-iteration construct, not the antipattern.
_LOOPS = (ast.For, ast.While, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


class _SequentialAwaitVisitor(ast.NodeVisitor):
    """Single O(n) pass: flag the first `await` of each enclosing loop.

    Maintains a stack of enclosing loops within the current function. The stack
    resets at function boundaries so a loop in an outer function never claims an
    `await` in a nested one. Each loop is flagged at most once.
    """

    def __init__(self) -> None:
        self._loops: list[ast.AST] = []
        self._flagged: set[int] = set()
        self.hits: list[ast.Await] = []

    @override
    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(node, _SCOPES):
            saved = self._loops
            self._loops = []
            super().generic_visit(node)
            self._loops = saved
        elif isinstance(node, _LOOPS):
            self._loops.append(node)
            super().generic_visit(node)
            self._loops.pop()
        elif isinstance(node, ast.Await):
            if self._loops:
                loop = self._loops[-1]
                if id(loop) not in self._flagged:
                    self._flagged.add(id(loop))
                    self.hits.append(node)
            super().generic_visit(node)
        else:
            super().generic_visit(node)
