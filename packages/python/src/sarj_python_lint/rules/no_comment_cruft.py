"""SARJ016: flag comment cruft — commented-out code, section banners, header preambles.

Code expresses the *what*; comments are reserved for the *why*. Three comment
shapes carry no *why* and are pure noise — they are detected deterministically
here (the fuzzier "this comment merely restates the code" judgment stays in the
readability audit, not this rule):

1. Commented-out code — a standalone comment whose text parses as Python:
       # return early_result
       # for row in rows:
   Delete it; git history remembers.

2. Section-banner / region markers:
       # ============================
       # region helpers
   Structure code with functions, not ASCII rules.

3. Leading file-header preamble — a run of 4+ standalone comment lines at the
   top of the file before any code. Use a module docstring for the *why*, not a
   block of `#` lines.

Deliberately NOT flagged: trailing/standalone *prose* comments (the legitimate
"why"), and directive comments — `# type:`, `# noqa`, `# sarj-noqa`,
`# pragma:`, `# pyright:`, `# mypy:`, `# fmt:`, `# isort:`, `# ruff:`,
`# nosec`, `# TODO`, `# FIXME`, shebangs, and coding declarations.

Suppress an intentional case with `# sarj-noqa: SARJ016 — <reason>`.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from typing import TYPE_CHECKING, override

from sarj_python_lint.rule_base import Diagnostic, Rule


if TYPE_CHECKING:
    from pathlib import Path


_LEADING_PREAMBLE_MIN = 4

_DIRECTIVE_PREFIXES = (
    "type:",
    "noqa",
    "sarj-noqa",
    "pragma:",
    "pyright:",
    "mypy:",
    "fmt:",
    "isort:",
    "ruff:",
    "pylint:",
    "flake8:",
    "nosec",
    "nosemgrep",
    "todo",
    "fixme",
    "hack",
    "xxx:",
    "-*-",
)

_LICENSE_RE = re.compile(
    r"copyright|license|licen[cs]ed|spdx|permission is hereby granted|"
    r"all rights reserved",
    re.IGNORECASE,
)

_BANNER_FULL_RE = re.compile(r"^[-=#*~_+.\s]{4,}$")
_BANNER_RUN_RE = re.compile(r"={4,}|-{4,}|#{4,}|\*{4,}|~{4,}")
_REGION_RE = re.compile(r"^(?:end)?region\b", re.IGNORECASE)

_CODE_STMT_RE = re.compile(
    r"^(?:import |from \S+ import |return\b|yield\b|await |"
    r"del |pass\b|break\b|continue\b|global |nonlocal |print\()"
)
# `assert`/`raise` double as English verbs ("assert this is true"), so they are
# only treated as code when the line also carries a code signal (an operator,
# paren, bracket, dot, or digit) — prose almost never does.
_RISKY_STMT_RE = re.compile(r"^(?:assert |raise )")
_CODE_SIGNAL_RE = re.compile(r"""[=()\[\]{}.:+\-*/%<>!&|@"']|\d""")
_CODE_HEADER_RE = re.compile(
    r"^(?:def |class |async def |if |elif |else:|for |while |with |"
    r"try:|except|finally:)"
)
_ASSIGN_OR_CALL_RE = re.compile(r"^[A-Za-z_][\w.\[\]]*\s*(?:=|:=|\+=|-=|\*=|/=)\s*\S|^[A-Za-z_][\w.]*\(")


def _comment_body(raw: str) -> str:
    return raw.lstrip("#").strip()


def _is_word_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def _is_directive(body: str) -> bool:
    low = body.lower()
    for prefix in _DIRECTIVE_PREFIXES:
        if not low.startswith(prefix):
            continue
        rest = low[len(prefix) :]
        if _is_word_char(prefix[-1]) and rest and _is_word_char(rest[0]):
            continue
        return True
    return False


def _is_banner(body: str) -> bool:
    if not body:
        return False
    if _BANNER_FULL_RE.match(body):
        return True
    if _BANNER_RUN_RE.search(body):
        return True
    return bool(_REGION_RE.match(body))


def _looks_like_code(body: str) -> bool:
    c = body.strip()
    if not c:
        return False
    if _CODE_STMT_RE.match(c):
        return _compiles(c)
    if _RISKY_STMT_RE.match(c):
        return bool(_CODE_SIGNAL_RE.search(c)) and _compiles(c)
    if _CODE_HEADER_RE.match(c):
        return _compiles(c + "\n    pass")
    if c.startswith("@"):
        return _compiles(c + "\ndef _f():\n    pass")
    if _ASSIGN_OR_CALL_RE.match(c):
        return _is_assign_or_call(c)
    return False


def _compiles(snippet: str) -> bool:
    try:
        ast.parse(snippet)
    except SyntaxError:
        return False
    return True


def _is_assign_or_call(snippet: str) -> bool:
    try:
        mod = ast.parse(snippet)
    except SyntaxError:
        return False
    if len(mod.body) != 1:
        return False
    stmt = mod.body[0]
    if isinstance(stmt, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
        return True
    return isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)


class NoCommentCruft(Rule):
    """Commented-out code, section banners, or a leading file-header comment block."""

    id: str = "no-comment-cruft"
    code: str = "SARJ016"
    description: str = (
        "Comment cruft (commented-out code, section banner, or file-header "
        "preamble) — delete it; code carries the what, comments only the why."
    )

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        try:
            standalone, first_code_line = _standalone_comments(source)
        except tokenize.TokenError, IndentationError, SyntaxError:
            return []
        diags: dict[int, Diagnostic] = {}
        for line, col, body in standalone:
            if _is_directive(body):
                continue
            msg = self._classify(body)
            if msg is not None:
                diags[line] = Diagnostic(path=path, line=line, col=col + 1, code=self.code, message=msg)
        self._flag_leading_preamble(standalone, first_code_line, path, diags)
        return [diags[k] for k in sorted(diags)]

    @staticmethod
    def _classify(body: str) -> str | None:
        if _is_banner(body):
            return "Section-banner / region comment — structure code with functions, not ASCII rules."
        if _looks_like_code(body):
            return "Commented-out code — delete it; git history remembers."
        return None

    def _flag_leading_preamble(
        self,
        standalone: list[tuple[int, int, str]],
        first_code_line: int,
        path: Path,
        diags: dict[int, Diagnostic],
    ) -> None:
        leading: list[tuple[int, int, str]] = []
        prev_line: int | None = None
        for line, col, body in standalone:
            if line >= first_code_line:
                break
            if body.startswith("!"):
                continue
            if _is_directive(body):
                continue
            if prev_line is not None and line != prev_line + 1:
                break
            leading.append((line, col, body))
            prev_line = line
        if any(_LICENSE_RE.search(body) for _, _, body in leading):
            return
        if len(leading) >= _LEADING_PREAMBLE_MIN:
            line, col, _ = leading[0]
            if line not in diags:
                diags[line] = Diagnostic(
                    path=path,
                    line=line,
                    col=col + 1,
                    code=self.code,
                    message=(
                        f"File-header comment preamble ({len(leading)} lines) — "
                        "use a module docstring for the why, not a block of comments."
                    ),
                )


_LAYOUT_TOKENS = frozenset({tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT})

_NON_CODE_TOKENS = _LAYOUT_TOKENS | frozenset({tokenize.COMMENT, tokenize.ENCODING, tokenize.ENDMARKER})


def _standalone_comments(source: str) -> tuple[list[tuple[int, int, str]], int]:
    """Return (standalone comments, first code line).

    A comment is standalone when it is the only content on its line. `first code
    line` is the row of the first real code token (a large sentinel if none).
    """
    out: list[tuple[int, int, str]] = []
    first_code_line = 1 << 30
    prev_end_row = 0
    readline = io.StringIO(source).readline
    for tok in tokenize.generate_tokens(readline):
        if tok.type == tokenize.COMMENT and tok.start[0] != prev_end_row:
            out.append((tok.start[0], tok.start[1], _comment_body(tok.string)))
        if tok.type not in _LAYOUT_TOKENS:
            prev_end_row = tok.end[0]
        if tok.type not in _NON_CODE_TOKENS:
            first_code_line = min(first_code_line, tok.start[0])
    return out, first_code_line
