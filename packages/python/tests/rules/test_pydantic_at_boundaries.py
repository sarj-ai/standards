from pathlib import Path

from sarj_python_lint.rule_base import Diagnostic
from sarj_python_lint.rules.pydantic_at_boundaries import PydanticAtBoundaries


def _check(source: str, path: str = "svc.py") -> list[Diagnostic]:
    return PydanticAtBoundaries().check(Path(path), source)


# --- Trigger 1: untyped dict returns ---------------------------------------


def test_flags_dict_str_any_return():
    src = """
from typing import Any

def build_payload(call) -> dict[str, Any]:
    return {"id": call.id}
"""
    diags = _check(src)
    assert len(diags) == 1
    assert "dict[str, Any]" in diags[0].message
    assert diags[0].code == "SARJ008"


def test_flags_dict_str_object_return():
    src = "def f() -> dict[str, object]:\n    return {}\n"
    assert len(_check(src)) == 1


def test_flags_bare_dict_and_typing_dict():
    src = """
from typing import Dict

def f() -> dict:
    return {}

def g() -> Dict:
    return {}

def h() -> Dict[str, Any]:
    return {}
"""
    assert len(_check(src)) == 3


def test_flags_list_of_untyped_dict():
    src = "def f() -> list[dict[str, Any]]:\n    return []\n"
    assert len(_check(src)) == 1


def test_flags_optional_untyped_dict():
    src = """
from typing import Any, Optional

def f() -> dict[str, Any] | None:
    return None

def g() -> Optional[dict[str, Any]]:
    return None
"""
    assert len(_check(src)) == 2


def test_flags_async_def():
    src = "async def f() -> dict[str, Any]:\n    return {}\n"
    assert len(_check(src)) == 1


def test_flags_method_in_class():
    src = """
class CallService:
    def summarize(self) -> dict[str, Any]:
        return {}
"""
    assert len(_check(src)) == 1


def test_skips_private_function():
    """Private/internal functions are not public boundaries — never flagged."""
    src = "def _build() -> dict[str, Any]:\n    return {}\n"
    assert _check(src) == []


def test_skips_pydantic_validator_hooks():
    """@model_validator/@field_validator take and return raw dict/values by contract."""
    src = """
from typing import Any
from pydantic import model_validator, field_validator

class M:
    @model_validator(mode="before")
    @classmethod
    def normalize(cls, data) -> dict[str, Any]:
        return data

    @field_validator("x")
    def coerce(cls, v) -> dict[str, Any]:
        return v
"""
    assert _check(src) == []


def test_allows_concrete_dict_value_types():
    src = """
def f() -> dict[str, str]:
    return {}

def g() -> dict[str, int]:
    return {}

def h() -> dict[str, list[int]]:
    return {}
"""
    assert _check(src) == []


def test_allows_typed_returns():
    src = """
def f() -> CallPayload: ...
def g() -> str: ...
def h() -> None: ...
def i() -> list[CallPayload]: ...
"""
    assert _check(src) == []


# --- tuple returns are NOT flagged (multiple return values are idiomatic) ----


def test_allows_heterogeneous_tuple_return():
    src = "def stop_call() -> tuple[bool, str | None]:\n    return True, None\n"
    assert _check(src) == []


def test_allows_typing_tuple_heterogeneous():
    src = """
from typing import Tuple

def f() -> Tuple[int, str]:
    return 1, "x"
"""
    assert _check(src) == []


def test_allows_homogeneous_tuples():
    src = """
def f() -> tuple[int, ...]:
    return ()

def g() -> tuple[str, str]:
    return "a", "b"

def h() -> tuple[int]:
    return (1,)
"""
    assert _check(src) == []


def test_allows_private_function_returning_tuple():
    src = "def _split() -> tuple[bool, str | None]:\n    return True, None\n"
    assert _check(src) == []


# --- Trigger 2: FastAPI route handlers ---------------------------------------


def test_flags_router_get_without_return_annotation():
    src = """
@router.get("/calls/{call_id}")
async def get_call(call_id: str):
    return {"id": call_id}
"""
    diags = _check(src)
    assert len(diags) == 1
    assert "no return annotation" in diags[0].message


def test_flags_app_post_without_return_annotation():
    src = """
@app.post("/calls")
def create_call(body: CreateCallRequest):
    return {"ok": True}
"""
    assert len(_check(src)) == 1


def test_flags_route_returning_untyped_dict():
    src = """
@router.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok"}
"""
    assert len(_check(src)) == 1


def test_allows_route_with_pydantic_return_annotation():
    src = """
@router.get("/calls/{call_id}")
async def get_call(call_id: str) -> CallResponse:
    return CallResponse(id=call_id)
"""
    assert _check(src) == []


def test_allows_route_with_response_model_kwarg():
    src = """
@router.get("/calls/{call_id}", response_model=CallResponse)
async def get_call(call_id: str):
    return {"id": call_id}
"""
    assert _check(src) == []


def test_ignores_non_router_receivers():
    """`client.get(...)` etc. is not a FastAPI route decorator."""
    src = """
@client.get("/upstream")
def fetch_upstream():
    return {}

@retry.post()
def push():
    return {}
"""
    assert _check(src) == []


def test_flags_named_router_receiver():
    src = """
@admin_router.delete("/orgs/{org_id}")
async def delete_org(org_id: str):
    return {"ok": True}
"""
    assert len(_check(src)) == 1


# --- Exclusions ---------------------------------------------------------------


def test_skips_test_files():
    src = "def f() -> dict[str, Any]:\n    return {}\n"
    assert _check(src, path="test_calls.py") == []
    assert _check(src, path="python/bulbul/tests/helpers.py") == []


def test_skips_overload_stubs():
    src = """
from typing import overload, Any

@overload
def f(x: int) -> dict[str, Any]: ...

@typing.overload
def f(x: str) -> dict[str, Any]: ...

def f(x) -> Payload:
    return Payload()
"""
    assert _check(src) == []


def test_plain_function_without_annotation_not_flagged():
    src = "def helper(x):\n    return x\n"
    assert _check(src) == []


def test_syntax_error_returns_empty():
    assert _check("def f(:\n") == []
