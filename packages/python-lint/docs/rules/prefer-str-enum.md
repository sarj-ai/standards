# `prefer-str-enum` (`SARJ006`)

> A Pydantic field annotated as a bare `str` whose name (`*_status`, `*_state`, `*_type`, `*_kind`) or a sibling `choices`/`states`/`STATUSES` class attribute strongly suggests a closed set — should be a `StrEnum`.

## What it catches

Inside any class **except** a subclass of `Enum`/`StrEnum`/`IntEnum`, an `AnnAssign` whose:

- Target name ends with `_status`, `_state`, `_type`, or `_kind`, OR
- The same class body has a `choices`/`states`/`STATUSES`/`values`/`allowed` attribute initialized to a tuple/list/set of string literals

AND the annotation is the bare type `str` (not `Literal[...]`, not `Union[...]`).

Per the original review, `Literal["a", "b"]` is acceptable — that's a proper closed set encoded in the type system.

## Why we encourage the alternative

A field declared `payment_status: str` accepts `"completed"`, `"copmleted"`, `""`, and `"DROP TABLE users;--"` interchangeably. The type system gives you no protection — and the bug only surfaces at runtime, often in a switch/match that silently falls through.

`StrEnum` (Python 3.11+) gives you a closed set the compiler enforces:

```py
from enum import StrEnum

class PaymentStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    REFUNDED = "refunded"

class Order(BaseModel):
    payment_status: PaymentStatus
```

Now:

- Pydantic rejects invalid values at parse time with a clear error.
- Pyright/MyPy narrows in `match` statements (`case PaymentStatus.PENDING:` makes the type `Literal[PaymentStatus.PENDING]`).
- The enum docstring lives where the values are declared, so reviewers know what each value means.
- Refactoring (renaming a status) is a structured change — Find Usages catches every site.

`Literal` is fine for one-off small sets where a class feels heavy. But for anything reused or stored, `StrEnum` is the standard.

## Bad

```py
class Order(BaseModel):
    payment_status: str = "pending"

# elsewhere
order.payment_status = "complete"  # typo — typechecker is silent
```

## Good — `StrEnum`

```py
from enum import StrEnum

class PaymentStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    REFUNDED = "refunded"

class Order(BaseModel):
    payment_status: PaymentStatus = PaymentStatus.PENDING
```

## Good — `Literal` (also accepted by this rule)

```py
from typing import Literal

class Order(BaseModel):
    payment_status: Literal["pending", "completed", "refunded"] = "pending"
```

## More examples

**Sibling `choices` attribute is the trigger** — caught even when the field name is innocuous:

```py
# Bad
class Notification(BaseModel):
    statuses = ("read", "unread", "muted")
    state: str  # ← flagged: sibling `statuses` makes the intent obvious
```

**Free-text field with `_state` suffix** — false positive territory; suppress:

```py
class Form(BaseModel):
    typing_state: str  # sarj-noqa: SARJ006 — free-text "I'm typing about X" status from user input, not a closed set
```

**Enum across the wire** — works with Pydantic serialization:

```py
class Status(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"

class User(BaseModel):
    status: Status

User(status="active")              # parses
User.model_validate_json('{"status": "active"}')  # parses
User(status="acitve")              # ValidationError
```

## When to suppress

- **Genuinely free-text fields that happen to have a typo-prone name** — e.g. `engagement_type: str` where the value is filled by the user in a free-form text box.
- **Untyped third-party API mirrors** — when you're modeling an upstream that doesn't document its enum, treat the field as `str` for now and convert later.

```py
class Webhook(BaseModel):
    event_type: str  # sarj-noqa: SARJ006 — Stripe sends arbitrary new event names; we don't enumerate
```

## References

- [`enum.StrEnum`](https://docs.python.org/3/library/enum.html#enum.StrEnum)
- [Pydantic — using `Enum`](https://docs.pydantic.dev/latest/concepts/types/#enums)
- [`typing.Literal`](https://docs.python.org/3/library/typing.html#typing.Literal)
