from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from sarj_python_lint.rules.prefer_str_enum import PreferStrEnum


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic


def _check(source: str, path: str = "<t>.py") -> list[Diagnostic]:
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


def test_flags_single_char_literal_cluster():
    """Single-character literals now cluster (`{0,30}` quantifier fix)."""
    src = """
def grade(g: str) -> int:
    if g == "a":
        return 4
    if g == "b":
        return 3
    return 0
"""
    diags = _check(src)
    assert len(diags) == 1
    assert "g" in diags[0].message


# --- Trigger 1: every token as a `_<token>` suffix ---------------------------


_CHOICE_TOKENS = [
    "status",
    "state",
    "kind",
    "role",
    "priority",
    "severity",
    "direction",
    "tier",
    "stage",
]


@pytest.mark.parametrize("token", _CHOICE_TOKENS)
def test_flags_every_token_as_suffix(token: str):
    src = f"""
from pydantic import BaseModel

class Rec(BaseModel):
    record_{token}: str
"""
    diags = _check(src)
    assert len(diags) == 1
    assert f"record_{token}" in diags[0].message


@pytest.mark.parametrize("token", _CHOICE_TOKENS)
def test_token_as_prefix_not_flagged(token: str):
    """A token must be the trailing segment; `status_code` etc. are free-form."""
    src = f"""
from pydantic import BaseModel

class Rec(BaseModel):
    {token}_code: str
"""
    assert _check(src) == []


@pytest.mark.parametrize("name", ["status_code", "state_id", "role_arn", "kind_name", "stage_name", "tier_list"])
def test_real_world_prefix_names_not_flagged(name: str):
    src = f"""
from pydantic import BaseModel

class Rec(BaseModel):
    {name}: str
"""
    assert _check(src) == []


@pytest.mark.parametrize("name", ["Status", "STATE", "Role", "Payment_Status", "call_DIRECTION"])
def test_choice_name_match_is_case_insensitive(name: str):
    src = f"""
from pydantic import BaseModel

class Rec(BaseModel):
    {name}: str
"""
    assert len(_check(src)) == 1


@pytest.mark.parametrize("ann", ["str | None", "Optional[str]", "list[str]", "dict[str, str]", "tuple[str, ...]"])
def test_non_bare_str_annotation_not_flagged(ann: str):
    """Only an annotation of exactly `str` fires; wrappers/unions do not."""
    src = f"""
from pydantic import BaseModel
from typing import Optional

class Rec(BaseModel):
    status: {ann}
"""
    assert _check(src) == []


def test_bare_assignment_without_annotation_not_flagged():
    """Only AnnAssign fields fire; a plain assignment is not annotated."""
    src = """
from pydantic import BaseModel

class Rec(BaseModel):
    status = "pending"
"""
    assert _check(src) == []


def test_field_col_offset_is_reported():
    src = """
from pydantic import BaseModel

class Rec(BaseModel):
    status: str
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].line == 5
    assert diags[0].col == 5


# --- Trigger 2: sibling choices attribute (all names / forms) -----------------


@pytest.mark.parametrize("attr", ["choices", "states", "statuses", "values", "allowed"])
def test_all_choices_attr_names_corroborate_free_name(attr: str):
    """A recognised sibling collection flags even a free-form str field."""
    src = f"""
from pydantic import BaseModel

class Rec(BaseModel):
    {attr} = ("a", "b")
    label: str
"""
    assert len(_check(src)) == 1


@pytest.mark.parametrize("coll", ['["a", "b"]', '("a", "b")', '{"a", "b"}'])
def test_choices_collection_list_tuple_set(coll: str):
    src = f"""
from pydantic import BaseModel

class Rec(BaseModel):
    choices = {coll}
    label: str
"""
    assert len(_check(src)) == 1


def test_choices_attr_name_is_case_insensitive():
    src = """
from pydantic import BaseModel

class Rec(BaseModel):
    CHOICES = ["a", "b"]
    label: str
"""
    assert len(_check(src)) == 1


def test_choices_attr_annassign_form_corroborates():
    src = """
from pydantic import BaseModel

class Rec(BaseModel):
    choices: list = ["a", "b"]
    label: str
"""
    assert len(_check(src)) == 1


def test_empty_choices_collection_still_corroborates():
    """An empty string-collection is still a string-collection (all() over [])."""
    src = """
from pydantic import BaseModel

class Rec(BaseModel):
    choices = []
    label: str
"""
    assert len(_check(src)) == 1


def test_choices_corroborates_all_free_form_fields():
    src = """
from pydantic import BaseModel

class Rec(BaseModel):
    choices = ["a", "b"]
    label: str
    caption: str
"""
    assert len(_check(src)) == 2


def test_non_string_collection_does_not_corroborate():
    src = """
from pydantic import BaseModel

class Rec(BaseModel):
    choices = [1, 2, 3]
    label: str
"""
    assert _check(src) == []


def test_scalar_string_choices_does_not_corroborate():
    src = """
from pydantic import BaseModel

class Rec(BaseModel):
    choices = "active"
    label: str
"""
    assert _check(src) == []


def test_unrecognised_collection_attr_does_not_corroborate():
    src = """
from pydantic import BaseModel

class Rec(BaseModel):
    options = ["a", "b"]
    label: str
"""
    assert _check(src) == []


def test_choices_attr_without_str_field_is_silent():
    src = """
from pydantic import BaseModel

class Rec(BaseModel):
    choices = ["a", "b"]
    count: int
"""
    assert _check(src) == []


# --- Trigger 3: comparison operators & membership forms -----------------------


@pytest.mark.parametrize("coll", ['["active", "pending"]', '{"active", "pending"}', '("active", "pending")'])
def test_flags_in_list_set_tuple_of_literals(coll: str):
    src = f"""
def handle(status: str) -> bool:
    return status in {coll}
"""
    assert len(_check(src)) == 1


def test_flags_not_in_cluster():
    src = """
def handle(status: str) -> bool:
    return status not in {"active", "pending"}
"""
    assert len(_check(src)) == 1


def test_in_single_literal_below_boundary():
    src = """
def handle(status: str) -> bool:
    return status in ("active",)
"""
    assert _check(src) == []


def test_empty_membership_container_not_flagged():
    src = """
def handle(status: str) -> bool:
    return status in ()
"""
    assert _check(src) == []


def test_pure_not_equal_cluster():
    src = """
def handle(status: str) -> int:
    if status != "active":
        return 1
    if status != "inactive":
        return 2
    return 0
"""
    assert len(_check(src)) == 1


def test_mixed_eq_and_in_operators_form_one_cluster():
    src = """
def handle(status: str) -> int:
    if status == "active":
        return 1
    if status in ("pending", "queued"):
        return 2
    return 0
"""
    diags = _check(src)
    assert len(diags) == 1
    assert "status" in diags[0].message


def test_exactly_two_distinct_literals_is_the_boundary():
    src = """
def handle(status: str) -> int:
    if status == "a":
        return 1
    if status == "b":
        return 2
    return 0
"""
    assert len(_check(src)) == 1


# --- Trigger 3: comparand shapes that are excluded ----------------------------


def test_call_comparand_excluded():
    src = """
def handle(status: str) -> int:
    if status == default():
        return 1
    if status == fallback():
        return 2
    return 0
"""
    assert _check(src) == []


def test_non_string_constant_comparand_excluded():
    src = """
def handle(code: str) -> int:
    if code == 1:
        return 1
    if code == 2:
        return 2
    return 0
"""
    assert _check(src) == []


def test_chained_comparison_excluded():
    src = """
def handle(status: str) -> bool:
    return "active" == status == "inactive"
"""
    assert _check(src) == []


def test_subscript_on_right_hand_side_excluded():
    src = """
def handle(status: str, data: dict) -> int:
    if status == data["x"]:
        return 1
    if status == data["y"]:
        return 2
    return 0
"""
    assert _check(src) == []


def test_empty_string_literal_disqualifies_cluster():
    src = """
def handle(status: str) -> int:
    if status == "":
        return 1
    if status == "active":
        return 2
    return 0
"""
    assert _check(src) == []


@pytest.mark.parametrize("lit", ["in-progress", "not_started", "v2", "a-b-c_d"])
def test_hyphen_and_underscore_tokens_still_cluster(lit: str):
    src = f"""
def handle(status: str) -> int:
    if status == "{lit}":
        return 1
    if status == "done":
        return 2
    return 0
"""
    assert len(_check(src)) == 1


def test_mid_uppercase_literal_disqualifies_cluster():
    src = """
def handle(status: str) -> int:
    if status == "activeState":
        return 1
    if status == "inactive":
        return 2
    return 0
"""
    assert _check(src) == []


def test_thirtyone_char_token_clusters():
    t1 = "a" + "b" * 30
    t2 = "c" + "d" * 30
    assert len(t1) == 31
    src = f"""
def handle(s: str) -> int:
    if s == "{t1}":
        return 1
    if s == "{t2}":
        return 2
    return 0
"""
    assert len(_check(src)) == 1


def test_thirtytwo_char_token_disqualifies_cluster():
    long = "a" + "b" * 31
    assert len(long) == 32
    src = f"""
def handle(s: str) -> int:
    if s == "active":
        return 1
    if s == "{long}":
        return 2
    return 0
"""
    assert _check(src) == []


# --- Trigger 3: scope attribution ---------------------------------------------


def test_nested_function_isolates_outer_cluster():
    """A comparison in a nested def is not attributed to the enclosing def."""
    src = """
def outer(status: str) -> int:
    if status == "active":
        return 1
    def inner(status: str) -> int:
        if status == "inactive":
            return 2
        return 0
    return inner(status)
"""
    assert _check(src) == []


def test_nested_function_has_its_own_cluster():
    src = """
def outer() -> int:
    def inner(status: str) -> int:
        if status == "active":
            return 1
        if status == "inactive":
            return 2
        return 0
    return inner("active")
"""
    assert len(_check(src)) == 1


def test_lambda_comparisons_are_not_attributed():
    """Lambdas are a skipped nested scope and are never given their own cluster."""
    src = """
def build():
    return lambda s: 1 if s == "active" else (2 if s == "inactive" else 0)
"""
    assert _check(src) == []


def test_async_function_cluster():
    src = """
async def handle(status: str) -> int:
    if status == "active":
        return 1
    if status == "inactive":
        return 2
    return 0
"""
    assert len(_check(src)) == 1


def test_method_self_attribute_cluster():
    src = """
class Worker:
    def run(self) -> int:
        if self.status == "active":
            return 1
        if self.status == "inactive":
            return 2
        return 0
"""
    diags = _check(src)
    assert len(diags) == 1
    assert "self.status" in diags[0].message


def test_deep_attribute_chain_clusters_on_full_key():
    src = """
def handle(ctx) -> int:
    if ctx.call.direction == "inbound":
        return 1
    if ctx.call.direction == "outbound":
        return 2
    return 0
"""
    diags = _check(src)
    assert len(diags) == 1
    assert "ctx.call.direction" in diags[0].message


def test_distinct_attribute_chains_do_not_cluster():
    src = """
def handle(o) -> int:
    if o.status == "active":
        return 1
    if o.state == "inactive":
        return 2
    return 0
"""
    assert _check(src) == []


def test_comparison_reports_first_line_and_col():
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
    assert diags[0].col == 8


# --- Edge cases: parsing, nesting, combined -----------------------------------


def test_empty_source_returns_empty():
    assert _check("") == []


def test_syntax_error_returns_empty():
    assert _check("def broken(:\n    pass\n") == []


def test_nested_classes_are_both_flagged():
    src = """
from pydantic import BaseModel

class Outer(BaseModel):
    status: str

    class Inner(BaseModel):
        kind: str
"""
    assert len(_check(src)) == 2


@pytest.mark.parametrize("base", ["Enum", "StrEnum", "IntEnum", "enum.StrEnum", "enum.Enum"])
def test_enum_bases_are_all_skipped(base: str):
    src = f"""
class Status({base}):
    state: str
    active = "active"
"""
    assert _check(src) == []


def test_non_enum_base_with_choice_field_still_flags():
    src = """
from pydantic import BaseModel

class Status(BaseModel):
    state: str
"""
    assert len(_check(src)) == 1


def test_field_and_cluster_coexist_and_sort_by_position():
    src = """
from pydantic import BaseModel

class Order(BaseModel):
    status: str

def route(kind: str) -> int:
    if kind == "a":
        return 1
    if kind == "b":
        return 2
    return 0
"""
    diags = _check(src)
    assert len(diags) == 2
    assert [d.line for d in diags] == sorted(d.line for d in diags)


# --- Adversarial: scope attribution across nested boundaries ------------------


def test_method_accumulates_across_a_nested_helper_def():
    """The method's own cluster must survive a nested def dropped in the middle:
    `active` + `pending` = 2 distinct -> one diag; the helper's `inactive` is
    isolated in its own cluster (below threshold)."""
    src = """
class W:
    def run(self, status: str) -> int:
        if status == "active":
            return 1
        def helper(status: str) -> int:
            if status == "inactive":
                return 2
            return 0
        if status == "pending":
            return 3
        return 0
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].line == 4
    assert "status" in diags[0].message


def test_class_nested_in_function_resets_the_cluster_scope():
    """A class body opened inside a function is its own (module-like) scope: the
    class-body comparison is not merged into the enclosing function's cluster,
    so neither side reaches the 2-literal threshold."""
    src = """
def outer(status):
    class C:
        y = status == "active"
    if status == "inactive":
        return 2
"""
    assert _check(src) == []


def test_comprehension_condition_clusters_within_its_function():
    """A comprehension makes no def/lambda node, so its `if` comparisons stay in
    the enclosing function's cluster."""
    src = """
def f(items):
    return [x for x in items if x == "active" or x == "inactive"]
"""
    assert len(_check(src)) == 1


def test_decorator_expression_comparisons_attribute_to_decorated_function():
    """Both comparisons live in a decorator call expression on the inner def;
    the DFS attributes them to that def's cluster, so the closed set still
    fires once."""
    src = """
def outer(status):
    @deco(status == "active" or status == "inactive")
    def inner():
        return 1
    return inner
"""
    assert len(_check(src)) == 1


# --- Adversarial: comparand shapes -------------------------------------------


def test_walrus_target_in_comparison_is_not_clustered():
    """A `(s := ...)` left-hand side is a NamedExpr, not a plain name/attribute,
    so it is excluded; the later bare `s` sees only one literal."""
    src = """
def handle(get) -> int:
    if (s := get()) == "active":
        return 1
    if s == "inactive":
        return 2
    return 0
"""
    assert _check(src) == []


def test_membership_against_a_variable_collection_not_flagged():
    src = """
def handle(status: str, allowed) -> bool:
    return status in allowed
"""
    assert _check(src) == []


def test_membership_against_non_literal_elements_not_flagged():
    src = """
def handle(status: str, a, b) -> bool:
    return status in (a, b)
"""
    assert _check(src) == []


def test_duplicate_literals_inside_in_tuple_do_not_reach_threshold():
    src = """
def handle(status: str) -> bool:
    return status in ("active", "active")
"""
    assert _check(src) == []


def test_yoda_and_not_equal_mix_into_one_cluster():
    src = """
def handle(status: str) -> int:
    if "active" == status:
        return 1
    if status != "inactive":
        return 2
    return 0
"""
    assert len(_check(src)) == 1


def test_upstream_contract_role_tuple_fires_as_closed_set():
    """An LLM message-role membership check is a genuine closed set; the rule
    fires (documenting that external-contract tuples are not exempted)."""
    src = """
def route(role: str) -> int:
    if role in ("user", "assistant", "system"):
        return 1
    return 0
"""
    assert len(_check(src)) == 1


# --- match/case string patterns cluster on the subject ----------------------


def test_match_case_string_patterns_should_cluster():
    src = """
def handle(status: str) -> int:
    match status:
        case "active":
            return 1
        case "inactive":
            return 2
    return 0
"""
    assert len(_check(src)) == 1


def test_match_case_or_patterns_cluster():
    src = """
def handle(status: str) -> int:
    match status:
        case "active" | "pending":
            return 1
        case "closed":
            return 2
    return 0
"""
    assert len(_check(src)) == 1


def test_match_case_single_string_pattern_does_not_cluster():
    src = """
def handle(status: str) -> int:
    match status:
        case "active":
            return 1
        case _:
            return 0
"""
    assert _check(src) == []


def test_match_case_class_patterns_do_not_cluster():
    src = """
def handle(event: object) -> int:
    match event:
        case Foo():
            return 1
        case Bar():
            return 2
    return 0
"""
    assert _check(src) == []


def test_match_case_combines_with_compare_on_same_subject():
    src = """
def handle(status: str) -> int:
    if status == "active":
        return 3
    match status:
        case "inactive":
            return 2
    return 0
"""
    assert len(_check(src)) == 1


def test_stringized_str_annotation_choice_field_should_flag():
    src = """
from pydantic import BaseModel

class Rec(BaseModel):
    status: "str"
"""
    assert len(_check(src)) == 1


# --- Adversarial: known defects (xfail, strict) ------------------------------


@pytest.mark.xfail(strict=True, reason="FP: metric/log field-name keys are not a value enum")
def test_metric_field_name_membership_should_not_cluster():
    src = """
def prune(k: str) -> bool:
    return k not in ["diff_ms", "total_ms"]
"""
    assert _check(src) == []
