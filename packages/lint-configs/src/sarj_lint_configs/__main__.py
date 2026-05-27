"""CLI for syncing bundled lint configs into a consumer repository."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import CONFIGS_DIR, __version__


CONFIG_NAMES: dict[str, tuple[str, str]] = {
    "ruff":    ("ruff.strict.toml",    ".ruff-strict.toml"),
    "pyright": ("pyright.strict.toml", ".pyright-strict.toml"),
    "eslint":  ("eslint.strict.mjs",   "eslint.strict.mjs"),
}


def _resolve_dest(dest_arg: str) -> Path:
    dest = Path(dest_arg).resolve()
    if not dest.is_dir():
        raise SystemExit(f"error: --dest {dest} is not a directory")
    return dest


def cmd_sync(args: argparse.Namespace) -> int:
    dest = _resolve_dest(args.dest)
    targets = [args.only] if args.only else list(CONFIG_NAMES)

    written = 0
    skipped = 0
    for name in targets:
        src_name, dst_name = CONFIG_NAMES[name]
        src = CONFIGS_DIR / src_name
        dst = dest / dst_name
        if dst.exists() and not args.force:
            print(f"skip:  {dst}  (exists; pass --force to overwrite)")
            skipped += 1
            continue
        shutil.copyfile(src, dst)
        print(f"wrote: {dst}")
        written += 1

    print(f"\nsynced {written}/{len(targets)} config(s); {skipped} skipped.")
    if written and "ruff" in targets:
        print(
            "\nnext: in your pyproject.toml, add:\n"
            '  [tool.ruff]\n'
            '  extend = ".ruff-strict.toml"\n'
        )
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    del args
    for name, (src, dst) in CONFIG_NAMES.items():
        full = CONFIGS_DIR / src
        size = full.stat().st_size if full.exists() else 0
        print(f"{name:8s}  {src:25s}  -> {dst:25s}  ({size:>5d} bytes)")
    return 0


def cmd_path(args: argparse.Namespace) -> int:
    src_name, _ = CONFIG_NAMES[args.name]
    print(CONFIGS_DIR / src_name)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sarj-lint-configs",
        description=f"sarj-ai maximally-strict lint configs (v{__version__})",
    )
    parser.add_argument(
        "--version", action="version", version=f"sarj-lint-configs {__version__}"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sync = sub.add_parser("sync", help="copy bundled configs into a repo")
    p_sync.add_argument("--dest", default=".", help="destination directory (default: cwd)")
    p_sync.add_argument("--only", choices=sorted(CONFIG_NAMES), help="sync just one config")
    p_sync.add_argument("--force", action="store_true", help="overwrite existing files")
    p_sync.set_defaults(func=cmd_sync)

    p_list = sub.add_parser("list", help="show available configs and target filenames")
    p_list.set_defaults(func=cmd_list)

    p_path = sub.add_parser("path", help="print the absolute path of a bundled config")
    p_path.add_argument("name", choices=sorted(CONFIG_NAMES))
    p_path.set_defaults(func=cmd_path)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
