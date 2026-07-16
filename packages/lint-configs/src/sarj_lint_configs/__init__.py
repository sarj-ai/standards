from __future__ import annotations

from importlib.resources import files
from pathlib import Path


__version__ = "0.4.0"

CONFIGS_DIR: Path = Path(str(files(__name__) / "configs"))

RUFF_STRICT: Path = CONFIGS_DIR / "ruff.strict.toml"
PYRIGHT_STRICT: Path = CONFIGS_DIR / "pyright.strict.json"
ESLINT_STRICT: Path = CONFIGS_DIR / "eslint.strict.mjs"
GITLEAKS: Path = CONFIGS_DIR / "gitleaks.toml"
EDITORCONFIG: Path = CONFIGS_DIR / "editorconfig"

__all__ = [
    "CONFIGS_DIR",
    "EDITORCONFIG",
    "ESLINT_STRICT",
    "GITLEAKS",
    "PYRIGHT_STRICT",
    "RUFF_STRICT",
    "__version__",
]
