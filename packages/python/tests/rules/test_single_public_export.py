from pathlib import Path
from typing import TYPE_CHECKING

from sarj_python_lint.rules.single_public_export import SinglePublicExport


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic


def _check(source: str, path: str = "multiproc_janitor.py") -> list[Diagnostic]:
    return SinglePublicExport().check(Path(path), source)


def test_single_class_matching_filename_is_clean():
    src = """
class MultiprocJanitor:
    def start(self) -> None: ...
"""
    assert _check(src) == []


def test_single_function_matching_filename_is_clean():
    src = """
def load_call_data() -> None: ...
"""
    assert _check(src, path="load_call_data.py") == []


def test_multiple_public_defs_out_of_scope():
    src = """
class MultiprocJanitor: ...

def gc_once() -> None: ...
"""
    assert _check(src, path="anything.py") == []


def test_filename_mismatch_flagged():
    src = """
class MultiprocJanitor: ...
"""
    diags = _check(src, path="prometheus_gc.py")
    assert len(diags) == 1
    assert "multiproc_janitor.py" in diags[0].message


def test_private_helpers_and_constants_ignored():
    src = """
THRESHOLD = 300

class MultiprocJanitor: ...

def _pid_alive(pid: int) -> bool: ...

_CACHE: dict[int, bool] = {}
"""
    assert _check(src) == []


def test_zero_public_defs_skipped():
    src = """
THRESHOLD = 300
_PATTERN = "x"
"""
    assert _check(src, path="constants.py") == []


def test_init_conftest_and_tests_skipped():
    src = """
class A: ...
class B: ...
"""
    assert _check(src, path="__init__.py") == []
    assert _check(src, path="conftest.py") == []
    assert _check(src, path="test_things.py") == []
    assert _check(src, path="pkg/tests/helpers.py") == []


def test_camel_case_acronym_boundary():
    src = """
class HTTPServerProbe: ...
"""
    assert _check(src, path="http_server_probe.py") == []
