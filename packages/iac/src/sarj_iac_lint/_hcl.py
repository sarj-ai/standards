r"""Tiny string/heredoc-aware scanning helpers shared across IaC rules.

These exist because the rules line-scan HCL without a parser: a `}` or `//`
inside a string literal, or `# foo` inside a heredoc body, must not be mistaken
for real syntax. The helpers stay deliberately small — they understand
double-quoted strings (with `\` escapes), `#` / `//` line comments, and
`<<EOT` / `<<-EOT` heredocs; nothing more.
"""

from __future__ import annotations

import re


_HEREDOC_RE = re.compile(r"<<-?\s*([A-Za-z_]\w*)")


def strip_inline_comment(line: str) -> str:
    """Truncate `line` at the first real `#`/`//` comment, ignoring ones in strings.

    String contents are preserved (so callers can still match literals such as a
    CIDR inside `"https://10.0.1.0/24"`); only a genuine comment is dropped.
    """
    in_str = False
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
        elif c == "#" or (c == "/" and i + 1 < n and line[i + 1] == "/"):
            return line[:i]
        i += 1
    return line


def mask_line(line: str) -> str:
    """Blank double-quoted string contents and drop comments, keeping structure.

    `description = "closes with }"` becomes `description = ""`, so brace counting
    and keyword matching see only real syntax — never characters inside a string.
    """
    out: list[str] = []
    in_str = False
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_str = False
                out.append('"')
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append('"')
        elif c == "#" or (c == "/" and i + 1 < n and line[i + 1] == "/"):
            break
        else:
            out.append(c)
        i += 1
    return "".join(out)


def heredoc_body_mask(lines: list[str]) -> list[bool]:
    """Per-line flags: True for every line sitting inside a heredoc body.

    The opener line (`body = <<EOT`) and the closing terminator line are False;
    only the literal text between them is masked, since that text is data, not
    HCL — its braces, `#`, and `key = value` shapes must be ignored.
    """
    mask = [False] * len(lines)
    term: str | None = None
    for idx, line in enumerate(lines):
        if term is not None:
            if line.strip() == term:
                term = None
            else:
                mask[idx] = True
            continue
        m = _HEREDOC_RE.search(mask_line(line))
        if m is not None:
            term = m.group(1)
    return mask
