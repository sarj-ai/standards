from __future__ import annotations

from importlib.resources import files
from pathlib import Path


__version__ = "0.1.0"

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
