"""sarj-python-lint — custom Python + SQL lint rules."""

from importlib.metadata import PackageNotFoundError, version


try:
    __version__ = version("sarj-python-lint")
except PackageNotFoundError:  # running from an uninstalled source tree
    __version__ = "0.0.0.dev0"
