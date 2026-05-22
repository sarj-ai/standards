# `prefer-discriminated-union` (`SARJ005`)

> A Pydantic `BaseModel` with a boolean status field (`success`, `ok`, `is_success`, `succeeded`, `failed`, `failure`) **and** two or more sibling `Optional` fields probably allows illegal states. Model it as a union of distinct variants instead.

## What it catches

A `class X(BaseModel)` whose body contains:

1. an `AnnAssign` like `success: bool`, AND
2. ≥ 2 sibling fields whose annotation is `Optional[T]`, `T | None`, or `Union[T, None]`,
3. and excluding fields whose name is in the noise allowlist (`metadata`, `meta`, `debug`, `debug_logs`, `extra`, `log`, `logs`, `traceback`, `request_id`, `trace_id`).

## Why we encourage the alternative

A flat "result envelope" with `success: bool` and a bunch of `Optional` siblings encodes ambiguity into the type:

```py
class Result(BaseModel):
    success: bool
    data: dict | None = None
    error: str | None = None
```

What does `Result(success=True, data=None, error=None)` mean? Both fields are optional, so the type system accepts it. So is `Result(success=False, data={"x": 1}, error="oops")` — clearly impossible in spirit, allowed by the schema.

A discriminated union eliminates the impossible states by construction:

```py
class Success(BaseModel):
    kind: Literal["success"]
    data: dict

class Failure(BaseModel):
    kind: Literal["failure"]
    error: str

Result = Success | Failure
```

Now:

- Pyright/MyPy narrows by `kind` automatically — `if r.kind == "success":` makes `r.data` available, no `assert r.data is not None` needed.
- Pydantic refuses invalid combinations at parse time.
- API consumers can't mistakenly pass `data` with `kind="failure"`.

This is "make illegal states unrepresentable" — the most reliable form of error handling.

## Bad

```py
from pydantic import BaseModel
from typing import Optional

class Result(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    retry_after: Optional[int] = None
```

## Good

```py
from pydantic import BaseModel
from typing import Literal, Annotated
from pydantic import Field

class Success(BaseModel):
    kind: Literal["success"]
    data: dict

class Failure(BaseModel):
    kind: Literal["failure"]
    error: str
    retry_after: int | None = None  # OK — retry_after is meaningful only on failure

Result = Annotated[Success | Failure, Field(discriminator="kind")]
```

## More examples

**Three states** — extend the same pattern:

```py
class Pending(BaseModel):
    kind: Literal["pending"]
    queued_at: datetime

class Active(BaseModel):
    kind: Literal["active"]
    started_at: datetime
    room_id: str

class Completed(BaseModel):
    kind: Literal["completed"]
    ended_at: datetime
    transcript: str

class Failed(BaseModel):
    kind: Literal["failed"]
    error: str

CallState = Annotated[
    Pending | Active | Completed | Failed,
    Field(discriminator="kind"),
]
```

**`status: str` with sibling optionals** — *not* flagged (the rule keys on `bool`). If you encode status as a string-enum + optional siblings, you have the same problem; the maintainers should still consider a discriminated union, but the rule deliberately stays narrow to keep false positives low.

**Just `success: bool` alone** — *not* flagged. The rule requires the bool field PLUS at least two optional siblings.

## When to suppress

Refactoring to a discriminated union is sometimes a non-trivial schema migration (existing API consumers may depend on the flat shape). Suppress with a tracking ticket:

```py
class LegacyResult(BaseModel):  # sarj-noqa: SARJ005 — migrating to Success|Failure in PROJ-1234
    success: bool
    data: dict | None = None
    error: str | None = None
```

## References

- [Pydantic — Discriminated unions](https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions)
- [Wikipedia — Tagged union](https://en.wikipedia.org/wiki/Tagged_union)
- [Alexis King — "Parse, don't validate"](https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/)
