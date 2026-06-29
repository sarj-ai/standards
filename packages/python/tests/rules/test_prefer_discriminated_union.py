from pathlib import Path
from typing import TYPE_CHECKING

from sarj_python_lint.rules.prefer_discriminated_union import PreferDiscriminatedUnion


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic


def _check(source: str) -> list[Diagnostic]:
    return PreferDiscriminatedUnion().check(Path("<t>.py"), source)


def test_flags_success_with_optional_fields():
    src = """
from pydantic import BaseModel
from typing import Optional

class Result(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
"""
    assert len(_check(src)) == 1


def test_flags_pipe_optional_syntax():
    src = """
from pydantic import BaseModel

class Result(BaseModel):
    success: bool
    payload: dict | None = None
    error: str | None = None
"""
    assert len(_check(src)) == 1


def test_allows_proper_union():
    src = """
from pydantic import BaseModel
from typing import Union

class Success(BaseModel):
    data: dict

class Failure(BaseModel):
    error: str
"""
    assert _check(src) == []


def test_allows_success_alone():
    src = """
from pydantic import BaseModel

class Heartbeat(BaseModel):
    success: bool
"""
    # Only one bool, no Optional siblings → don't flag
    assert _check(src) == []


# --- Trigger 2: bool-tuple results ---


def test_flags_bool_tuple_return():
    src = """
def fetch() -> tuple[bool, str]:
    return True, "ok"
"""
    diags = _check(src)
    assert len(diags) == 1
    assert "bool-tuple" in diags[0].message


def test_flags_bool_tuple_return_any_order():
    src = """
def fetch() -> tuple[str | None, bool]:
    return None, False
"""
    assert len(_check(src)) == 1


def test_flags_bool_tuple_optional_payload():
    src = """
def fetch() -> tuple[bool, dict | None]:
    return False, None
"""
    assert len(_check(src)) == 1


def test_flags_typing_tuple_spelling():
    src = """
from typing import Tuple

def fetch() -> Tuple[bool, str]:
    return True, "ok"
"""
    assert len(_check(src)) == 1


def test_flags_async_bool_tuple_return():
    src = """
async def fetch() -> tuple[bool, str]:
    return True, "ok"
"""
    assert len(_check(src)) == 1


def test_allows_non_bool_tuple_return():
    src = """
def pair() -> tuple[str, int]:
    return "a", 1
"""
    assert _check(src) == []


def test_allows_plain_bool_return():
    src = """
def is_ready() -> bool:
    return True
"""
    assert _check(src) == []


def test_allows_variadic_bool_tuple_return():
    src = """
def flags() -> tuple[bool, ...]:
    return (True, False)
"""
    assert _check(src) == []


def test_allows_three_element_tuple_return():
    src = """
def triple() -> tuple[bool, str, int]:
    return True, "a", 1
"""
    assert _check(src) == []


# --- Trigger 3: nullable cluster + discriminator-ish field ---


def test_flags_status_plus_nullable_cluster():
    src = """
from pydantic import BaseModel
from datetime import datetime

class Call(BaseModel):
    status: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    error: str | None = None
"""
    diags = _check(src)
    assert len(diags) == 1
    assert "per-state models" in diags[0].message


def test_flags_dataclass_nullable_cluster_optional_spelling():
    src = """
from dataclasses import dataclass
from typing import Literal, Optional

@dataclass
class Job:
    state: Literal["pending", "running", "done"]
    result: Optional[str] = None
    error: Optional[str] = None
    duration: Optional[float] = None
"""
    assert len(_check(src)) == 1


def test_flags_str_enum_discriminator():
    src = """
from enum import StrEnum
from pydantic import BaseModel

class CallStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"

class Call(BaseModel):
    status: CallStatus
    room_id: str | None = None
    transcript: str | None = None
    error: str | None = None
"""
    assert len(_check(src)) == 1


def test_allows_nullable_cluster_without_discriminator():
    src = """
from pydantic import BaseModel

class Profile(BaseModel):
    nickname: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
"""
    assert _check(src) == []


def test_allows_two_nullables_with_status():
    src = """
from pydantic import BaseModel

class Call(BaseModel):
    status: str
    started_at: str | None = None
    error: str | None = None
"""
    assert _check(src) == []


def test_allows_non_string_discriminator():
    src = """
from pydantic import BaseModel

class Counts(BaseModel):
    status: int
    a: str | None = None
    b: str | None = None
    c: str | None = None
"""
    assert _check(src) == []


def test_allows_plain_class_nullable_cluster():
    src = """
class Plain:
    status: str
    a: str | None = None
    b: str | None = None
    c: str | None = None
"""
    assert _check(src) == []


def test_no_double_flag_when_both_class_triggers_match():
    src = """
from pydantic import BaseModel

class Result(BaseModel):
    success: bool
    status: str
    data: dict | None = None
    error: str | None = None
    detail: str | None = None
"""
    assert len(_check(src)) == 1


def test_syntax_error_returns_empty():
    assert _check("def broken(:\n") == []


def test_allows_filter_input_and_partial_update_dtos():
    src = """
from pydantic import BaseModel

class ListCallsInput(BaseModel):
    status: str
    date_from: str | None = None
    date_to: str | None = None
    phone_number: str | None = None

class UpdateCall(BaseModel):
    status: str
    started_at: str | None = None
    ended_at: str | None = None
    report: str | None = None
"""
    assert _check(src) == []


def test_allows_single_value_literal_union_arm():
    src = """
from pydantic import BaseModel
from typing import Literal

class CallCompletedWebhookPayload(BaseModel):
    type: Literal["complete"] = "complete"
    call_started: str | None = None
    response_body: dict | None = None
    call_data: dict | None = None
"""
    assert _check(src) == []


def test_allows_single_value_literal_arm_optional_spelling():
    src = """
from pydantic import BaseModel
from typing import Literal, Optional

class Created(BaseModel):
    kind: Literal["created"]
    a: Optional[str] = None
    b: Optional[str] = None
    c: Optional[str] = None
"""
    assert _check(src) == []


def test_flags_multi_value_literal_discriminator():
    src = """
from pydantic import BaseModel
from typing import Literal

class Job(BaseModel):
    status: Literal["pending", "running", "done"]
    result: str | None = None
    error: str | None = None
    duration: float | None = None
"""
    assert len(_check(src)) == 1


def test_does_not_flag_non_bool_status_type():
    """`success: BoolishFlag` must not trip the bool trigger (parsed-node check)."""
    src = """
from pydantic import BaseModel
from typing import Optional

class Result(BaseModel):
    success: BoolishFlag
    data: Optional[str] = None
    error: Optional[str] = None
"""
    assert _check(src) == []


def test_flags_unioned_bool_status():
    """`success: bool | None` still counts as a bool status field."""
    src = """
from pydantic import BaseModel
from typing import Optional

class Result(BaseModel):
    success: bool | None = None
    data: Optional[str] = None
    error: Optional[str] = None
"""
    assert len(_check(src)) == 1
