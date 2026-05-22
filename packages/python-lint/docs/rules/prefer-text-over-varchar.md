# `sarj-prefer-text-over-varchar`

> Use `TEXT` instead of `VARCHAR(n)` in Postgres. The length cap doesn't buy you anything Postgres-side, and changing it later is a table-rewrite migration.

## What it catches

A regex match for `(?i)VARCHAR\(` in any file matching the consumer's `files:` glob (typically Postgres migrations).

## Why we encourage the alternative

In Postgres, `VARCHAR(n)`, `VARCHAR`, and `TEXT` are stored identically — they all use the same `varlena` representation, with no storage difference. The `n` cap is just a CHECK constraint:

| Type | Storage | Constraint |
|---|---|---|
| `TEXT` | varlena | none |
| `VARCHAR` (no length) | varlena | none |
| `VARCHAR(n)` | varlena | length ≤ n |
| `CHAR(n)` | blank-padded fixed | length = n (avoid — wastes space) |

So `VARCHAR(255)` gives you nothing performance-wise vs `TEXT`. But it costs you in two ways:

1. **Changing the cap is expensive.** Raising `VARCHAR(255)` to `VARCHAR(500)` requires a full table rewrite (`ALTER COLUMN … TYPE`). On a large table that's an outage. `TEXT` has no cap to bump.
2. **The cap is the wrong layer.** Length validation belongs in the application (Pydantic `Field(max_length=...)`, Zod `.max(n)`) where it's a structured error, not in the schema where it surfaces as a generic `value too long` from the driver.

Per the original review on the docs proposal: "just use TEXT". No `CHECK (length(col) <= n)` substitute — let the application own the rule.

## Bad

```sql
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    full_name VARCHAR(100)
);
```

## Good

```sql
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    full_name TEXT
);
```

Pair the column with application-level validation:

```py
class CreateUser(BaseModel):
    email: EmailStr = Field(..., max_length=255)
    full_name: str | None = Field(None, max_length=100)
```

## More examples

**ALTER COLUMN type change** — same rule, also flagged:

```sql
-- Bad
ALTER TABLE users ALTER COLUMN bio TYPE VARCHAR(500);

-- Good
ALTER TABLE users ALTER COLUMN bio TYPE TEXT;
```

**Imported from a legacy schema** — when migrating, switch to `TEXT` as part of the move:

```sql
-- Original (in some other DB)
-- CREATE TABLE legacy_users (email VARCHAR(254));

-- Postgres migration
CREATE TABLE IF NOT EXISTS users (
    email TEXT NOT NULL UNIQUE
);
```

## When to suppress

Genuine fixed-width domains (ISO country codes, currency codes, ICAO airport codes) — `CHAR(n)` may even be appropriate. Exclude the specific migration with a comment:

```yaml
- id: sarj-prefer-text-over-varchar
  files: '^svcs/db/db/migrations/.*\.sql$'
  exclude: |
    (?x)^(
      svcs/db/db/migrations/20240101_create_currency_table\.sql$
    )
```

In practice the simpler call is still `TEXT` + `CHECK (length(col) = 3)`.

## References

- [Postgres docs — Character Types](https://www.postgresql.org/docs/current/datatype-character.html)
- [Postgres wiki — "Don't Do This: `varchar(n)`"](https://wiki.postgresql.org/wiki/Don%27t_Do_This#Don.27t_use_varchar.28n.29_by_default)
- [Depesz — "TEXT vs varchar"](https://www.depesz.com/2010/03/02/charx-vs-varcharx-vs-varchar-vs-text/)
