"""CLI: sarj-python-lint check --rule <id> [--rule <id2>] <files>"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from sarj_python_lint import __version__
from sarj_python_lint.rule_base import Diagnostic, is_suppressed
from sarj_python_lint.rules import REGISTRY


def _baseline_key(d: Diagnostic) -> str:
    """Identity of a violation that survives line shifts (no line number).

    Keyed on path + code + message; the message embeds the offending symbol
    (e.g. the field name), so a moved-but-unchanged violation stays baselined
    while a genuinely new one is not.
    """
    return f"{d.path}\x00{d.code}\x00{d.message}"


def _load_baseline(path: Path) -> dict[str, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, int] = {}
    for e in data:
        out[f"{e['path']}\x00{e['code']}\x00{e['message']}"] = e.get("count", 1)
    return out


def _dump_baseline(path: Path, diags: list[Diagnostic]) -> None:
    counts = Counter(_baseline_key(d) for d in diags)
    payload = [
        {"path": p, "code": c, "message": m, "count": counts[k]}
        for k in sorted(counts)
        for p, c, m in [k.split("\x00")]
    ]
    path.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")


def _apply_baseline(
    diags: list[Diagnostic], baseline: dict[str, int]
) -> list[Diagnostic]:
    """Drop up to `count` occurrences of each baselined key; keep the surplus."""
    seen: Counter[str] = Counter()
    kept: list[Diagnostic] = []
    for d in diags:
        key = _baseline_key(d)
        if seen[key] < baseline.get(key, 0):
            seen[key] += 1
            continue
        kept.append(d)
    return kept


SKIP_DIR_NAMES = {
    "node_modules",
    ".venv",
    "venv",
    ".git",
    "dist",
    "build",
    ".next",
    "coverage",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".turbo",
    ".yarn",
    ".pnpm-store",
}


def _expand_paths(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        if not p.exists():
            continue
        if p.is_file():
            out.append(p)
            continue
        for child in p.rglob("*.py"):
            if not child.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in child.parts):
                continue
            try:
                if child.stat().st_size > 500_000:
                    continue
            except OSError:
                continue
            out.append(child)
    return out


def _check(rule_ids: list[str], paths: list[Path]) -> list[Diagnostic]:
    unknown = [rid for rid in rule_ids if rid not in REGISTRY]
    if unknown:
        sys.stderr.write(f"unknown rule(s): {', '.join(unknown)}\n")
        sys.stderr.write(f"available: {', '.join(sorted(REGISTRY))}\n")
        raise SystemExit(2)
    rules = [REGISTRY[rid]() for rid in rule_ids]
    expanded = _expand_paths(paths)
    diags: list[Diagnostic] = []
    for p in expanded:
        try:
            source = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        source_lines = source.splitlines()
        for rule in rules:
            for d in rule.check(p, source):
                if is_suppressed(source_lines, d.line, d.code):
                    continue
                diags.append(d)
    return diags


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sarj-python-lint",
        description="Custom Python + SQL lint rules.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    check_p = sub.add_parser("check", help="Run rules over files.")
    check_p.add_argument(
        "--rule",
        action="append",
        required=True,
        help="Rule ID (repeat for multiple).",
    )
    check_p.add_argument(
        "--baseline",
        type=Path,
        help="Suppress violations listed in this baseline JSON (fire on new code only).",
    )
    check_p.add_argument(
        "--write-baseline",
        type=Path,
        metavar="FILE",
        help="Write all current violations to FILE as a baseline and exit 0.",
    )
    check_p.add_argument(
        "--exit-zero",
        action="store_true",
        help="Report violations but always exit 0 (warn mode — does not fail CI).",
    )
    check_p.add_argument("files", nargs="+", type=Path)

    sub.add_parser("list-rules", help="List available rule IDs.")

    args = parser.parse_args(argv)

    if args.cmd == "list-rules":
        for rid, cls in sorted(REGISTRY.items()):
            inst = cls()
            sys.stdout.write(f"{inst.code:8}  {rid:40}  {inst.description}\n")
        return 0

    diags = _check(args.rule, args.files)

    if args.write_baseline is not None:
        _dump_baseline(args.write_baseline, diags)
        sys.stderr.write(
            f"wrote {len(diags)} baseline entries to {args.write_baseline}\n"
        )
        return 0

    if args.baseline is not None:
        diags = _apply_baseline(diags, _load_baseline(args.baseline))

    for d in diags:
        sys.stdout.write(d.format() + "\n")
    if args.exit_zero:
        return 0
    return 1 if diags else 0


if __name__ == "__main__":
    sys.exit(main())
