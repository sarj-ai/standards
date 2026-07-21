from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from sarj_python_lint.rules.prefer_timedelta_for_durations import (
    PreferTimedeltaForDurations,
)


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic


def _check(source: str) -> list[Diagnostic]:
    return PreferTimedeltaForDurations().check(Path("<t>.py"), source)


def test_flags_int_param_named_seconds():
    src = "def schedule(timeout_seconds: int) -> None: ...\n"
    diags = _check(src)
    assert len(diags) == 1
    assert "timedelta" in diags[0].message


def test_flags_float_field_named_interval_ms():
    src = """
class Settings:
    retry_interval_ms: float = 250.0
"""
    assert len(_check(src)) == 1


def test_flags_optional_int_duration():
    src = "def f(ttl: int | None = None) -> None: ...\n"
    assert len(_check(src)) == 1


def test_flags_optional_subscript_duration():
    src = "def f(backoff_seconds: Optional[float]) -> None: ...\n"
    assert len(_check(src)) == 1


def test_allows_timedelta_annotation():
    src = "def schedule(timeout: timedelta) -> None: ...\n"
    assert _check(src) == []


def test_flags_pydantic_constrained_duration():
    src = """
class Settings:
    api_timeout_s: NonNegativeFloat = 30.0
    retry_interval_seconds: PositiveInt = 5
"""
    assert len(_check(src)) == 2


def test_flags_annotated_duration():
    src = "def f(delay_seconds: Annotated[int, Field(ge=0)]) -> None: ...\n"
    assert len(_check(src)) == 1


def test_flags_pydantic_constrained_optional_duration():
    src = "def f(ttl: PositiveInt | None = None) -> None: ...\n"
    assert len(_check(src)) == 1


def test_allows_wall_clock_singular_components():
    src = """
class TimeEdge:
    hour: int
    minute: int
    second: int
"""
    assert _check(src) == []


def test_allows_percentage_and_rate_named_floats():
    src = """
class Report:
    average_duration_trend_percentage: float
    interval_hit_rate: float
"""
    assert _check(src) == []


def test_allows_count_like_names():
    src = """
def f(retry_count: int, num_days: int, page_size: int) -> None: ...
"""
    assert _check(src) == []


def test_allows_calendar_units_and_instants():
    src = """
def f(retention_months: int, created_at: int, expires_timestamp: float) -> None: ...
"""
    assert _check(src) == []


def test_allows_unannotated_param():
    src = "def f(timeout_seconds=30): ...\n"
    assert _check(src) == []


def test_ignores_non_numeric_annotation():
    src = "def f(timeout_seconds: str) -> None: ...\n"
    assert _check(src) == []


# ---------------------------------------------------------------------------
# Positive family: every time-unit token in the rule's `_UNIT_RE`, as a
# function parameter annotated `int`, must be flagged exactly once.
# ---------------------------------------------------------------------------

_UNIT_NAMES = [
    "timeout_seconds",
    "poll_secs",
    "poll_milliseconds",
    "poll_millis",
    "poll_ms",
    "wait_minutes",
    "wait_mins",
    "wait_hours",
    "sleep_hrs",
    "retry_days",
    "timeout",
    "request_timeout",
    "poll_interval",
    "interval",
    "ttl",
    "delay",
    "retry_delay",
    "backoff",
    "backoff_ms",
    "duration",
    "call_duration",
    "cooldown",
    "cooldown_seconds",
    "expires_in",
]


@pytest.mark.parametrize("name", _UNIT_NAMES)
@pytest.mark.parametrize("numeric", ["int", "float"])
def test_flags_every_unit_token_as_param(name: str, numeric: str):
    src = f"def f({name}: {numeric}) -> None: ...\n"
    diags = _check(src)
    assert len(diags) == 1
    assert name in diags[0].message
    assert numeric in diags[0].message
    assert "timedelta" in diags[0].message


@pytest.mark.parametrize("name", _UNIT_NAMES)
def test_flags_every_unit_token_as_field(name: str):
    src = f"class C:\n    {name}: int = 1\n"
    assert len(_check(src)) == 1


@pytest.mark.parametrize("name", _UNIT_NAMES)
def test_flags_every_unit_token_module_level_field(name: str):
    src = f"{name}: float\n"
    assert len(_check(src)) == 1


# ---------------------------------------------------------------------------
# Positive family: numeric-annotation shapes that must resolve to a duration.
# ---------------------------------------------------------------------------

_NUMERIC_SHAPES = [
    "int",
    "float",
    "int | None",
    "None | int",
    "float | None",
    "Optional[int]",
    "Optional[float]",
    "typing.Optional[int]",
    "Annotated[int, Field(ge=0)]",
    "Annotated[float, 'meta']",
    "Optional[Annotated[int, Field(ge=0)]]",
    "Annotated[int | None, Field()]",
    "PositiveInt",
    "NonNegativeInt",
    "NegativeInt",
    "NonPositiveInt",
    "StrictInt",
    "PositiveFloat",
    "NonNegativeFloat",
    "NegativeFloat",
    "NonPositiveFloat",
    "StrictFloat",
    "PositiveInt | None",
    "Optional[NonNegativeFloat]",
    "pydantic.PositiveInt",
]


@pytest.mark.parametrize("annotation", _NUMERIC_SHAPES)
def test_flags_all_numeric_annotation_shapes(annotation: str):
    src = f"def f(timeout_seconds: {annotation}) -> None: ...\n"
    assert len(_check(src)) == 1


# ---------------------------------------------------------------------------
# Negative family: a real duration name but excluded by `_EXCLUDE_RE`.
# ---------------------------------------------------------------------------

_EXCLUDED_NAMES = [
    "timeout_count",
    "interval_index",
    "duration_id",
    "num_seconds",
    "n_ms",
    "delay_size",
    "backoff_limit",
    "ttl_version",
    "timeout_idx",
    "interval_len",
    "duration_length",
    "delay_offset",
    "timeout_at",
    "interval_ts",
    "duration_months",
    "backoff_years",
    "timeout_percentage",
    "interval_percent",
    "delay_pct",
    "duration_ratio",
    "timeout_rate",
    "interval_trend",
    "duration_epoch",
    "cooldown_timestamp",
]


@pytest.mark.parametrize("name", _EXCLUDED_NAMES)
def test_excluded_names_not_flagged(name: str):
    src = f"def f({name}: int) -> None: ...\n"
    assert _check(src) == []


# ---------------------------------------------------------------------------
# Negative family: non-duration numeric fields (no unit token at all).
# ---------------------------------------------------------------------------

_NON_DURATION_NAMES = [
    "retry_count",
    "page_size",
    "port",
    "max_retries",
    "buffer_length",
    "offset",
    "n_items",
    "version",
    "user_id",
    "row_index",
    "http_status",
    "capacity",
]


@pytest.mark.parametrize("name", _NON_DURATION_NAMES)
def test_non_duration_numeric_not_flagged(name: str):
    src = f"def f({name}: int) -> None: ...\n"
    assert _check(src) == []


# ---------------------------------------------------------------------------
# Negative family: wall-clock singular components are positions, not durations.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["hour", "minute", "second", "day", "week", "month"])
def test_singular_wall_clock_not_flagged(name: str):
    src = f"def f({name}: int) -> None: ...\n"
    assert _check(src) == []


# ---------------------------------------------------------------------------
# Negative family: already-`timedelta`-typed durations are the goal state.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "annotation",
    [
        "timedelta",
        "datetime.timedelta",
        "timedelta | None",
        "Optional[timedelta]",
    ],
)
@pytest.mark.parametrize("name", ["timeout_seconds", "ttl", "retry_delay"])
def test_timedelta_typed_not_flagged(name: str, annotation: str):
    src = f"def f({name}: {annotation}) -> None: ...\n"
    assert _check(src) == []


# ---------------------------------------------------------------------------
# Negative family: duration name but a non-numeric annotation.
# ---------------------------------------------------------------------------

_NON_NUMERIC_ANNOTATIONS = [
    "str",
    "bytes",
    "bool",
    "list[int]",
    "dict[str, int]",
    "MyDuration",
    "Optional[str]",
    "str | None",
    "Annotated[str, Field()]",
    "'int'",
]


@pytest.mark.parametrize("annotation", _NON_NUMERIC_ANNOTATIONS)
def test_duration_name_non_numeric_annotation_not_flagged(annotation: str):
    src = f"def f(timeout_seconds: {annotation}) -> None: ...\n"
    assert _check(src) == []


def test_string_forward_ref_annotation_is_not_resolved():
    """String (forward-ref) annotations are opaque to the AST rule — a known limit."""
    src = 'def f(delay_seconds: "int") -> None: ...\n'
    assert _check(src) == []


# ---------------------------------------------------------------------------
# Explicit false-positive guards named in the task.
# ---------------------------------------------------------------------------


def test_num_seconds_display_str_not_flagged():
    src = "class C:\n    num_seconds_display: str\n"
    assert _check(src) == []


def test_max_retries_int_not_flagged():
    src = "class C:\n    max_retries: int = 3\n"
    assert _check(src) == []


def test_timestamp_field_is_an_instant_not_a_duration():
    src = "class C:\n    timestamp: float\n    created_timestamp: int\n"
    assert _check(src) == []


def test_seconds_name_typed_str_not_flagged():
    src = "class C:\n    duration_seconds: str\n"
    assert _check(src) == []


# ---------------------------------------------------------------------------
# Edge cases: parsing, scope, argument kinds.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("src", ["", "   \n\n", "# just a comment\n", "\n\n\n"])
def test_empty_or_trivial_source_returns_empty(src: str):
    assert _check(src) == []


def test_syntax_error_returns_empty():
    src = "def f(timeout_seconds: int  ->\n"
    assert _check(src) == []


def test_async_function_param_flagged():
    src = "async def f(timeout_seconds: int) -> None: ...\n"
    assert len(_check(src)) == 1


def test_posonly_and_kwonly_params_flagged():
    src = "def f(timeout_seconds: int, /, *, retry_delay: float) -> None: ...\n"
    assert len(_check(src)) == 2


def test_plain_assignment_not_flagged():
    src = "timeout_seconds = 30\n"
    assert _check(src) == []


def test_module_level_annassign_flagged():
    src = "poll_interval_seconds: int = 5\n"
    assert len(_check(src)) == 1


def test_attribute_target_annassign_flagged():
    src = "self.timeout_seconds: int = 5\n"
    assert len(_check(src)) == 1


def test_nested_function_param_flagged():
    src = """
def outer() -> None:
    def inner(retry_delay: float) -> None: ...
"""
    assert len(_check(src)) == 1


def test_method_self_not_flagged():
    src = """
class C:
    def m(self, timeout_seconds: int) -> None: ...
"""
    assert len(_check(src)) == 1


# ---------------------------------------------------------------------------
# Multiple diagnostics: count and ascending-line ordering.
# ---------------------------------------------------------------------------


def test_multiple_diagnostics_counted_and_sorted():
    src = """
timeout_seconds: int = 1
retry_delay: float = 2.0
poll_interval: int = 3
"""
    diags = _check(src)
    assert len(diags) == 3
    lines = [d.line for d in diags]
    assert lines == sorted(lines)


def test_mixed_flag_and_allow_in_one_class():
    src = """
class Settings:
    timeout_seconds: int
    retry_count: int
    poll_interval_ms: float
    created_at: int
"""
    diags = _check(src)
    assert len(diags) == 2
    assert {d.line for d in diags} == {3, 5}


# ---------------------------------------------------------------------------
# Line / column precision.
# ---------------------------------------------------------------------------


def test_param_line_and_col():
    src = "def schedule(timeout_seconds: int) -> None: ...\n"
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].line == 1
    assert diags[0].col == 14


def test_field_line_and_col():
    src = "x_ms: int = 5\n"
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].line == 1
    assert diags[0].col == 1


def test_diagnostic_code_is_sarj014():
    src = "def f(timeout_seconds: int) -> None: ...\n"
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ014"
