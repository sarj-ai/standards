"""Resolve the installed package version, with a source-tree fallback."""

from importlib.metadata import PackageNotFoundError, version


def _resolve_version() -> str:
    """Return the installed distribution version, or a dev sentinel from source.

    Returns:
        The distribution version string, or ``"0.0.0.dev0"`` when the package is
        not installed (running straight from a source checkout).

    """
    try:
        return version("sarj-python-lint")
    except PackageNotFoundError:
        return "0.0.0.dev0"


__version__ = _resolve_version()
