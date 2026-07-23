"""Base types and shared SQL text utilities for sarj-sql-lint rules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
import re


type Statement = list[tuple[int, str]]
"""A statement as `(lineno, text)` fragments — one per source line it spans."""


_SARJ_NOQA_RE = re.compile(
    r"--\s*sarj-noqa(?::\s*([A-Za-z0-9_, ]+))?",
    re.IGNORECASE,
)
_NON_NEWLINE = re.compile(r"[^\n]")
_DOLLAR_OPEN_RE = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$")


def is_suppressed(source_lines: list[str], line: int, code: str) -> bool:
    """Report whether the diagnostic's line carries a `-- sarj-noqa[: CODE]` comment.

    Returns:
        True when the line is suppressed for `code`.

    """
    if line < 1 or line > len(source_lines):
        return False
    m = _SARJ_NOQA_RE.search(source_lines[line - 1])
    if m is None:
        return False
    codes_str = m.group(1)
    if not codes_str:
        return True
    codes = {c.strip().upper() for c in codes_str.split(",") if c.strip()}
    return code.upper() in codes


def _blank(segment: str) -> str:
    """Replace every char with a space, keeping newlines so offsets are preserved.

    Returns:
        `segment` with every non-newline character turned into a space.

    """
    return _NON_NEWLINE.sub(" ", segment)


def _scan_quoted(source: str, start: int, quote: str) -> int:
    """Index just past a `quote`-delimited run starting at `start`, honoring `''`/`""`.

    Returns:
        The index one past the closing quote, or `len(source)` if unterminated.

    """
    n = len(source)
    j = start + 1
    while j < n:
        if source[j] == quote:
            if j + 1 < n and source[j + 1] == quote:
                j += 2
                continue
            return j + 1
        j += 1
    return n


def mask_sql(source: str) -> str:
    """Blank out comments, string literals, dollar-quoted bodies and quoted identifiers.

    The returned text has the same length and line structure as `source`, with the
    contents of `--`/`/* */` comments, `'...'` literals, `$tag$...$tag$` strings and
    `"..."` identifiers replaced by spaces. Routing rule scanning through this masked
    text keeps keywords inside comments/strings/identifiers from ever matching.

    Returns:
        A same-length copy of `source` with those spans blanked.

    """
    out: list[str] = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        pair = source[i : i + 2]
        if pair == "--":
            end = source.find("\n", i)
            end = n if end == -1 else end
        elif pair == "/*":
            close = source.find("*/", i + 2)
            end = n if close == -1 else close + 2
        elif ch in {"'", '"'}:
            end = _scan_quoted(source, i, ch)
        elif ch == "$":
            m = _DOLLAR_OPEN_RE.match(source, i)
            if m is None:
                out.append(ch)
                i += 1
                continue
            tag = m.group(0)
            close = source.find(tag, m.end())
            end = n if close == -1 else close + len(tag)
        else:
            out.append(ch)
            i += 1
            continue
        out.append(_blank(source[i:end]))
        i = end
    return "".join(out)


def split_statements(masked: str) -> list[Statement]:
    """Split already-masked SQL into `;`-delimited statements.

    Operates on `mask_sql` output so a `;` inside a string/comment (now blank) never
    splits a statement. Each statement is a list of `(lineno, text)` fragments.

    Returns:
        One `Statement` per `;`-delimited run, in source order.

    """
    statements: list[Statement] = []
    current: Statement = []
    for lineno, raw in enumerate(masked.splitlines(), start=1):
        line = raw
        while ";" in line:
            head, _, line = line.partition(";")
            current.append((lineno, head))
            statements.append(current)
            current = []
        if line:
            current.append((lineno, line))
    if current:
        statements.append(current)
    return statements


def locate(statement: Statement, offset: int) -> tuple[int, int]:
    r"""Map a char `offset` into `"\n".join(text)` back to a 1-based `(line, col)`.

    Returns:
        The 1-based `(line, col)` for `offset`, clamped to the statement's end.

    """
    pos = 0
    for lineno, text in statement:
        if offset <= pos + len(text):
            return lineno, offset - pos + 1
        pos += len(text) + 1
    last_lineno, last_text = statement[-1]
    return last_lineno, len(last_text) + 1


@dataclass(frozen=True, slots=True)
class Diagnostic:
    path: Path
    line: int
    col: int
    code: str
    message: str

    def format(self) -> str:
        return f"{self.path}:{self.line}:{self.col}: {self.code} {self.message}"


class Rule(ABC):
    id: str
    code: str
    description: str

    @abstractmethod
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        raise NotImplementedError
