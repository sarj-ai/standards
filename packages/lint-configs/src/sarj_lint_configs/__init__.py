from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from importlib.resources import files
from pathlib import Path


try:
    __version__ = version("sarj-lint-configs")
except PackageNotFoundError:  # running from an uninstalled source tree
    __version__ = "0.0.0.dev0"

CONFIGS_DIR: Path = Path(str(files(__name__) / "configs"))

RUFF_STRICT: Path = CONFIGS_DIR / "ruff.strict.toml"
PYRIGHT_STRICT: Path = CONFIGS_DIR / "pyright.strict.json"
ESLINT_STRICT: Path = CONFIGS_DIR / "eslint.strict.mjs"

__all__ = [
    "CONFIGS_DIR",
    "ESLINT_STRICT",
    "PYRIGHT_STRICT",
    "RUFF_STRICT",
    "__version__",
]
