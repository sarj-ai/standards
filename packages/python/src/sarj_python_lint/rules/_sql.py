"""Shared SQL-literal helpers for the SQL-aware store-lint rules (SARJ018-021).

These rules scan raw SQL embedded in Python string literals for keywords
(`JOIN`, `COUNT`, `ON CONFLICT`, `*`, ...). Scanning the raw text conflates SQL
*code* with SQL string-literal *values*: `WHERE p = 'join'` holds no JOIN, a
`--` inside a quoted value is not a comment, and a backtick inside a value is not
a BigQuery table quote. `strip_sql_noise` neutralizes both classes of noise
before any keyword or comment scan.
"""

from __future__ import annotations

import ast


def sql_string_value(node: ast.expr) -> str | None:
    """Reconstruct a (possibly `+`-concatenated) string literal, else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = sql_string_value(node.left)
        right = sql_string_value(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def strip_sql_noise(text: str) -> str:
    """Blank out SQL string-literal contents and comment bodies.

    A single left-to-right scan, so precedence between strings and comments is
    correct: a `--` or quote inside a string literal is protected (masked as
    string data, never read as a comment), and a quote inside a comment is
    ignored. Every masked character becomes a space except newlines, which are
    preserved so line offsets — and therefore diagnostic positions — do not
    shift. Doubled quotes (`''` / `""`) are SQL's in-string escape and keep the
    scanner inside the literal.
    """
    out = list(text)
    n = len(text)
    i = 0
    while i < n:
        ch = text[i]
        if ch in {"'", '"'}:
            out[i] = " "
            i += 1
            while i < n:
                c = text[i]
                if c == ch:
                    if i + 1 < n and text[i + 1] == ch:
                        out[i] = out[i + 1] = " "
                        i += 2
                        continue
                    out[i] = " "
                    i += 1
                    break
                if c != "\n":
                    out[i] = " "
                i += 1
            continue
        if ch == "-" and i + 1 < n and text[i + 1] == "-":
            while i < n and text[i] != "\n":
                out[i] = " "
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            out[i] = out[i + 1] = " "
            i += 2
            while i < n and not (text[i] == "*" and i + 1 < n and text[i + 1] == "/"):
                if text[i] != "\n":
                    out[i] = " "
                i += 1
            if i < n:
                out[i] = " "
                i += 1
                if i < n:
                    out[i] = " "
                    i += 1
            continue
        i += 1
    return "".join(out)
