from pathlib import Path

import pytest

from sarj_python_lint.rules.prefer_str_enum import PreferStrEnum


def _check(source: str, path: str = "<t>.py") -> list:
    return PreferStrEnum().check(Path(path), source)


def test_flags_choice_attr_with_str_field():
    src = """
from pydantic import BaseModel

class Order(BaseModel):
    statuses = ("pending", "shipped", "delivered")
    status: str = "pending"
"""
    assert len(_check(src)) == 1


def test_flags_status_suffix_name():
    src = """
from pydantic import BaseModel

class Order(BaseModel):
    payment_status: str
"""
    assert len(_check(src)) == 1


def test_allows_literal_type():
    """Per user L234: Literal[...] is acceptable."""
    src = """
from pydantic import BaseModel
from typing import Literal

class Order(BaseModel):
    status: Literal["pending", "shipped", "delivered"]
"""
    assert _check(src) == []


def test_allows_str_for_free_text_field():
    src = """
from pydantic import BaseModel

class User(BaseModel):
    name: str
    email: str
"""
    assert _check(src) == []


def test_does_not_flag_enum_class():
    src = """
from enum import StrEnum

class Status(StrEnum):
    pending = "pending"
"""
    assert _check(src) == []


# --- Trigger 1: widened name heuristic ---------------------------------------


@pytest.mark.parametrize(
    "field",
    [
        "status",
        "state",
        "kind",
        "role",
        "priority",
        "severity",
        "direction",
        "tier",
        "stage",
    ],
)
def test_flags_exact_choice_like_name(field: str):
    src = f"""
from pydantic import BaseModel

class Config(BaseModel):
    {field}: str
"""
    diags = _check(src)
    assert len(diags) == 1
    assert field in diags[0].message


@pytest.mark.parametrize(
    "field",
    # Free-form-prone tokens removed from the name heuristic (too noisy).
    ["type", "provider", "level", "mode", "category", "channel", "method", "format", "source", "language", "env"],
)
def test_allows_dropped_choice_tokens(field: str):
    """These names are too free-form to flag on the name alone (need corroboration)."""
    src = f"""
from pydantic import BaseModel

class Config(BaseModel):
    {field}: str
"""
    assert _check(src) == []


def test_flags_choice_like_suffix_name():
    src = """
from pydantic import BaseModel

class Call(BaseModel):
    payment_status: str
    call_direction: str
"""
    assert len(_check(src)) == 2


@pytest.mark.parametrize("field", ["name", "email", "provider_name", "description", "url"])
def test_allows_non_choice_like_names(field: str):
    src = f"""
from pydantic import BaseModel

class User(BaseModel):
    {field}: str
"""
    assert _check(src) == []


def test_allows_choice_like_name_with_non_str_annotation():
    src = """
from pydantic import BaseModel

class Config(BaseModel):
    provider: Provider
    language: Literal["en", "ar"]
"""
    assert _check(src) == []


# --- Trigger 2: literal defaults (plain and Field(default=...)) ---------------


def test_flags_choice_like_name_with_plain_literal_default():
    src = """
from pydantic import BaseModel

class Job(BaseModel):
    priority: str = "high"
"""
    assert len(_check(src)) == 1


def test_flags_choice_like_name_with_field_default():
    src = """
from pydantic import BaseModel, Field

class Job(BaseModel):
    status: str = Field(default="pending")
"""
    assert len(_check(src)) == 1


def test_allows_literal_default_on_free_text_name():
    src = """
from pydantic import BaseModel

class User(BaseModel):
    nickname: str = "anon"
"""
    assert _check(src) == []


# --- Trigger 3: comparison clusters -------------------------------------------


def test_flags_comparison_cluster():
    src = """
def handle(status: str) -> int:
    if status == "active":
        return 1
    if status == "inactive":
        return 2
    return 0
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].line == 3
    assert "status" in diags[0].message
    assert "StrEnum" in diags[0].message


def test_flags_attribute_comparison_cluster():
    src = """
def handle(call) -> int:
    if call.direction == "inbound":
        return 1
    if call.direction != "outbound":
        return 2
    return 0
"""
    diags = _check(src)
    assert len(diags) == 1
    assert "call.direction" in diags[0].message


def test_flags_in_tuple_of_literals():
    src = """
def handle(status: str) -> bool:
    return status in ("active", "pending")
"""
    assert len(_check(src)) == 1


def test_allows_single_comparison():
    src = """
def handle(status: str) -> bool:
    return status == "active"
"""
    assert _check(src) == []


def test_allows_repeated_same_literal():
    src = """
def handle(status: str) -> bool:
    if status == "active":
        pass
    return status == "active"
"""
    assert _check(src) == []


def test_allows_uppercase_literal_cluster():
    src = """
def handle(code: str) -> int:
    if code == "ACTIVE":
        return 1
    if code == "INACTIVE":
        return 2
    return 0
"""
    assert _check(src) == []


def test_allows_long_literal_cluster():
    src = """
def handle(msg: str) -> int:
    if msg == "this-is-a-very-long-free-text-message-not-a-token":
        return 1
    if msg == "another-extremely-long-free-text-message-here-too":
        return 2
    return 0
"""
    assert _check(src) == []


def test_one_bad_literal_disqualifies_the_cluster():
    src = """
def handle(status: str) -> int:
    if status == "active":
        return 1
    if status == "Not A Token!":
        return 2
    if status == "inactive":
        return 3
    return 0
"""
    assert _check(src) == []


def test_ignores_fstring_and_attribute_comparands():
    src = """
def handle(status: str, expected: str) -> int:
    if status == f"{expected}-suffix":
        return 1
    if status == Status.ACTIVE:
        return 2
    return 0
"""
    assert _check(src) == []


def test_ignores_subscripted_left_hand_side():
    src = """
def handle(payload: dict) -> int:
    if payload["status"] == "active":
        return 1
    if payload["status"] == "inactive":
        return 2
    return 0
"""
    assert _check(src) == []


def test_distinct_variables_do_not_form_a_cluster():
    src = """
def handle(a: str, b: str) -> int:
    if a == "active":
        return 1
    if b == "inactive":
        return 2
    return 0
"""
    assert _check(src) == []


def test_clusters_do_not_span_functions():
    src = """
def first(status: str) -> bool:
    return status == "active"

def second(status: str) -> bool:
    return status == "inactive"
"""
    assert _check(src) == []


def test_module_level_comparisons_not_flagged():
    src = """
import sys

if sys.platform == "linux":
    X = 1
elif sys.platform == "darwin":
    X = 2
"""
    assert _check(src) == []


def test_yoda_comparisons_count():
    src = """
def handle(status: str) -> int:
    if "active" == status:
        return 1
    if "inactive" == status:
        return 2
    return 0
"""
    assert len(_check(src)) == 1


@pytest.mark.parametrize("path", ["test_handlers.py", "pkg/tests/handlers.py"])
def test_comparison_cluster_skipped_in_test_files(path: str):
    src = """
def handle(status: str) -> int:
    if status == "active":
        return 1
    if status == "inactive":
        return 2
    return 0
"""
    assert _check(src, path=path) == []


def test_name_heuristic_still_applies_in_test_files():
    """Only the comparison-cluster trigger is test-file-scoped."""
    src = """
from pydantic import BaseModel

class Order(BaseModel):
    payment_status: str
"""
    assert len(_check(src, path="test_models.py")) == 1
