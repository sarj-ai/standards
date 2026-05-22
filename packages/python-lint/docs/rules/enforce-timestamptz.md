# `enforce-timestamptz` (`SARJ101`)

> Postgres SQL must use `TIMESTAMPTZ` (or `TIMESTAMP WITH TIME ZONE`). Naïve `TIMESTAMP` discards the offset on INSERT and silently corrupts data for non-UTC clients.

## What it catches

The token `TIMESTAMP` in a `.sql` source, not immediately followed (case-insensitive, whitespace tolerant) by `TZ` or `WITH TIME ZONE`. Comment lines (`-- ...`, `/* ... */`) are skipped.

## Why we encourage the alternative

Postgres has two related types with **wildly different semantics**:

| Type | Stores | Behavior on INSERT |
|---|---|---|
| `TIMESTAMP WITHOUT TIME ZONE` (a.k.a. `TIMESTAMP`) | Wall-clock value | Inserted offset is *silently discarded* |
| `TIMESTAMP WITH TIME ZONE` (a.k.a. `TIMESTAMPTZ`) | UTC instant | Inserted offset is *applied* to convert to UTC |

Internally both are 8 bytes — TIMESTAMPTZ does **not** store the offset, it stores the UTC instant. The "WITH TIME ZONE" name is unfortunate, but the semantics are exactly what you want: the database stores a definite moment in time.

The bug surface for `TIMESTAMP WITHOUT TIME ZONE`:

- A client in Tokyo inserts `2026-05-22T09:00:00+09:00`. The database stores `2026-05-22 09:00:00` (Tokyo wall-clock).
- A client in Riyadh inserts `2026-05-22T09:00:00+03:00`. The database stores `2026-05-22 09:00:00` (Riyadh wall-clock).
- Both rows now compare equal. There is no way to recover which was which.

With TIMESTAMPTZ both inserts resolve to distinct UTC instants and ordering / equality / interval math all work correctly.

Standard advice from the Postgres wiki: **always use TIMESTAMPTZ**, even when your application is "always UTC" — the cost is zero bytes and the safety is real.

## Bad

```sql
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    placed_at TIMESTAMP NOT NULL,                  -- discards offset
    completed_at TIMESTAMP                          -- same
);
```

## Good

```sql
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    placed_at TIMESTAMPTZ NOT NULL DEFAULT now(),  -- stores UTC instant
    completed_at TIMESTAMPTZ
);
```

`TIMESTAMP WITH TIME ZONE` is also accepted (same type, more verbose name):

```sql
CREATE TABLE meetings (
    id BIGSERIAL PRIMARY KEY,
    starts_at TIMESTAMP WITH TIME ZONE NOT NULL
);
```

## More examples

**Schema migration adding a column** — caught:

```sql
-- Bad
ALTER TABLE orders ADD COLUMN refunded_at TIMESTAMP;

-- Good
ALTER TABLE orders ADD COLUMN refunded_at TIMESTAMPTZ;
```

**Functions / casts** — caught:

```sql
-- Bad
SELECT now()::TIMESTAMP FROM orders;

-- Good
SELECT now()::TIMESTAMPTZ FROM orders;
-- or simply:
SELECT now() FROM orders;
```

**Stored intervals** — `INTERVAL` is not flagged (it's a duration, not a moment).

## When to suppress

Only when you're modeling a *floating wall-clock time* (e.g. a recurring meeting at "9 AM in the user's local time" where the local time, not the instant, is the source of truth). That's rare; if you suppress, document the rationale:

```sql
-- The "9 AM local" recurring schedule — store as TIMESTAMP WITHOUT TIME ZONE on purpose.
ALTER TABLE recurring_meetings
    ADD COLUMN starts_at_local TIMESTAMP NOT NULL; -- intentional: wall-clock, not instant
```

(In sarj-python-lint this rule fires from `pre-commit` text matching, so the suppression mechanism is to exclude the file via `exclude:` in `.pre-commit-config.yaml`, since SQL doesn't honor `# sarj-noqa:` comments.)

## References

- [Postgres docs — Date/Time Types](https://www.postgresql.org/docs/current/datatype-datetime.html)
- [Postgres wiki — Don't Do This: `timestamp (without time zone)`](https://wiki.postgresql.org/wiki/Don%27t_Do_This#Don.27t_use_timestamp_.28without_time_zone.29)
- [Brandur — "Storing time, an interactive guide"](https://brandur.org/fragments/postgres-timezones)
