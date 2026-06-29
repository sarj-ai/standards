from pathlib import Path

from sarj_python_lint.rules.prefer_timedelta_for_durations import (
    PreferTimedeltaForDurations,
)


def _check(source: str) -> list:
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
