from pathlib import Path
from typing import TYPE_CHECKING

from sarj_python_lint.rules.stepdown import Stepdown


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic


def _check(source: str, path: str = "svc.py") -> list[Diagnostic]:
    return Stepdown().check(Path(path), source)


def test_clean_stepdown_module():
    src = """
def handle_request(payload: dict) -> str:
    parsed = _parse(payload)
    return _render(parsed)

def _parse(payload: dict) -> dict:
    return _normalize(payload)

def _render(parsed: dict) -> str:
    return str(parsed)

def _normalize(payload: dict) -> dict:
    return payload
"""
    assert _check(src) == []


def test_private_above_caller_fires():
    src = """
def _parse(payload: dict) -> dict:
    return payload

def handle_request(payload: dict) -> str:
    return str(_parse(payload))
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].line == 2
    assert "_parse" in diags[0].message
    assert "handle_request" in diags[0].message


def test_helper_below_first_caller_but_above_second_is_clean():
    src = """
def first(x: int) -> int:
    return _shared(x)

def _shared(x: int) -> int:
    return x + 1

def second(x: int) -> int:
    return _shared(x)
"""
    assert _check(src) == []


def test_class_method_ordering_fires():
    src = """
class Handler:
    def _load(self) -> dict:
        return {}

    def handle(self) -> dict:
        return self._load()
"""
    diags = _check(src)
    assert len(diags) == 1
    assert "_load" in diags[0].message
    assert "handle" in diags[0].message


def test_class_clean_ordering():
    src = """
class Handler:
    def handle(self) -> dict:
        return self._load()

    def _load(self) -> dict:
        return {}
"""
    assert _check(src) == []


def test_mutual_recursion_skipped():
    src = """
def _even(n: int) -> bool:
    return True if n == 0 else _odd(n - 1)

def _odd(n: int) -> bool:
    return False if n == 0 else _even(n - 1)

def classify(n: int) -> bool:
    return _even(n)
"""
    assert _check(src) == []


def test_indirect_recursion_skipped():
    src = """
def _a(n: int) -> int:
    return _b(n)

def _b(n: int) -> int:
    return _c(n)

def _c(n: int) -> int:
    return _a(n)

def run(n: int) -> int:
    return _a(n)
"""
    assert _check(src) == []


def test_self_recursion_still_fires():
    src = """
def _countdown(n: int) -> int:
    return n if n == 0 else _countdown(n - 1)

def run(n: int) -> int:
    return _countdown(n)
"""
    diags = _check(src)
    assert len(diags) == 1
    assert "_countdown" in diags[0].message


def test_type_checking_only_usage_skipped():
    src = """
from typing import TYPE_CHECKING

def _make_client() -> object:
    return object()

if TYPE_CHECKING:
    _CLIENT_FACTORY = _make_client

def run() -> object:
    return _make_client()
"""
    assert _check(src) == []


def test_decorator_reference_pins_helper():
    src = """
def _traced(fn):
    return fn

@_traced
def handle() -> None: ...

def rewrap(fn):
    return _traced(fn)
"""
    assert _check(src) == []


def test_default_arg_reference_pins_helper():
    src = """
def _default_limit() -> int:
    return 10

def fetch(limit: int = _default_limit()) -> int:
    return limit

def refetch() -> int:
    return fetch(_default_limit())
"""
    assert _check(src) == []


def test_annotation_reference_pins_helper():
    src = """
def _sentinel() -> object:
    return object()

def apply(fn: _sentinel) -> None: ...

def run() -> None:
    _sentinel()
"""
    assert _check(src) == []


def test_dunder_first_is_clean():
    src = """
class Service:
    def __init__(self) -> None:
        self.state = self._initial_state()

    def run(self) -> None:
        self._step()

    def _initial_state(self) -> dict:
        return {}

    def _step(self) -> None: ...
"""
    assert _check(src) == []


def test_dunder_never_flagged():
    src = """
class Service:
    def __call__(self) -> None: ...

    def run(self) -> None:
        self.__call__()
"""
    assert _check(src) == []


def test_unused_private_def_not_flagged():
    src = """
def _orphan() -> None: ...

def run() -> None: ...
"""
    assert _check(src) == []


def test_module_level_reference_pins_helper():
    src = """
def _build_registry() -> dict:
    return {}

REGISTRY = _build_registry()

def lookup(key: str) -> object:
    return _build_registry()[key]
"""
    assert _check(src) == []


def test_class_body_attribute_reference_pins_method():
    src = """
def _handler() -> None: ...

class Dispatcher:
    default = staticmethod(_handler)

    def run(self) -> None:
        _handler()
"""
    assert _check(src) == []


def test_property_and_abstractmethod_exempt():
    src = """
from abc import abstractmethod
from functools import cached_property

class Base:
    @property
    def _conn(self) -> object:
        return object()

    @cached_property
    def _pool(self) -> object:
        return object()

    @abstractmethod
    def _hook(self) -> None: ...

    def run(self) -> None:
        self._hook()
        print(self._conn, self._pool)
"""
    assert _check(src) == []


def test_overload_style_duplicate_defs_skipped():
    src = """
class Model:
    @property
    def _value(self) -> int:
        return 1

    @_value.setter
    def _value(self, v: int) -> None: ...

    def bump(self) -> None:
        self._value = self._value + 1
"""
    assert _check(src) == []


def test_shadowing_local_binding_skipped():
    src = """
def _config() -> dict:
    return {}

def setup() -> None:
    _config = {"a": 1}
    print(_config)

def run() -> dict:
    return _config()
"""
    assert _check(src) == []


def test_self_attribute_store_shadows_method_name():
    src = """
class Service:
    def _factory(self) -> object:
        return object()

    def __init__(self) -> None:
        self._factory = object

    def run(self) -> object:
        return self._factory()
"""
    assert _check(src) == []


def test_class_calling_module_helper_below_is_clean():
    src = """
class Runner:
    def run(self) -> dict:
        return _load()

def _load() -> dict:
    return {}
"""
    assert _check(src) == []


def test_module_helper_above_class_caller_fires():
    src = """
def _load() -> dict:
    return {}

class Runner:
    def run(self) -> dict:
        return _load()
"""
    diags = _check(src)
    assert len(diags) == 1
    assert "_load" in diags[0].message
    assert "Runner" in diags[0].message


def test_private_class_not_flagged():
    src = """
class _State:
    pass

def run() -> _State:
    return _State()
"""
    assert _check(src) == []


def test_syntax_error_returns_empty():
    assert _check("def broken(:\n") == []


def test_test_paths_skipped():
    src = """
def _helper() -> int: ...

def test_x():
    _helper()
"""
    assert _check(src, path="test_things.py") == []
    assert _check(src, path="pkg/tests/helpers.py") == []
