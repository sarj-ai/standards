# `sarj-ban-postgres-enums`

> Don't `CREATE TYPE foo AS ENUM (...)` in Postgres migrations. Use `TEXT` with a `CHECK` constraint (or a lookup table) instead.

## What it catches

A regex match for `(?i)CREATE TYPE.*AS ENUM` in any file matching the consumer's `files:` glob (typically `^svcs/db/db/migrations/.*\.sql$`).

## Why we encourage the alternative

Postgres native `ENUM` types are deceptively attractive — they take less storage than `TEXT`, and the values look type-safe. But they have three operational sharp edges:

1. **You can't remove a value.** `ALTER TYPE foo DROP VALUE 'x'` does not exist in Postgres. Once a value is in the enum, you're stuck with it forever (or you do a full type-swap migration, which on a large table is an outage).
2. **`ALTER TYPE foo ADD VALUE` can't run inside a transaction in PG ≤ 11**, and even in newer versions it can't run inside a serializable transaction with concurrent writers. That makes migrations brittle.
3. **The application-side enum and the database-side enum drift independently.** When you add a value in Python's `StrEnum`, you must also add it via a separate migration — they're not generated from a single source.

A `TEXT NOT NULL CHECK (status IN ('a', 'b', 'c'))` column:

- Takes the same space in practice (Postgres TOAST handles short strings efficiently).
- Can be migrated freely — `ALTER TABLE … DROP CONSTRAINT …; ALTER TABLE … ADD CONSTRAINT …;` is a single online operation.
- Lets the application code own the source of truth (the Python `StrEnum`), with a thin CHECK constraint as a backstop.

If you need a normalized lookup table with metadata per value (`order_status_table(id, label, description, is_terminal)`), do that — and keep the column as a foreign-key `TEXT`/`INTEGER` referencing the table.

## Bad

```sql
CREATE TYPE order_status AS ENUM ('pending', 'shipped', 'delivered');

CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    status order_status NOT NULL DEFAULT 'pending'
);
```

## Good — `TEXT` + `CHECK`

```sql
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'shipped', 'delivered'))
);
```

## Good — lookup table

When the enum has metadata per value:

```sql
CREATE TABLE order_status (
    status TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    is_terminal BOOLEAN NOT NULL DEFAULT false
);

INSERT INTO order_status (status, label, is_terminal) VALUES
    ('pending',   'Pending',   false),
    ('shipped',   'Shipped',   false),
    ('delivered', 'Delivered', true);

CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending' REFERENCES order_status(status)
);
```

## More examples

**Existing native enum that's hard to remove** — at minimum stop adding new ones; if the table is small, write a swap migration:

```sql
-- 1. add new column
ALTER TABLE orders ADD COLUMN status_v2 TEXT
    CHECK (status_v2 IN ('pending', 'shipped', 'delivered'));

-- 2. backfill
UPDATE orders SET status_v2 = status::text;

-- 3. swap
ALTER TABLE orders DROP COLUMN status;
ALTER TABLE orders RENAME COLUMN status_v2 TO status;
ALTER TABLE orders ALTER COLUMN status SET NOT NULL;

-- 4. drop the type once unused
DROP TYPE order_status;
```

## When to suppress

If you've decided as a team to use native enums in a particular subsystem (e.g. low-churn vocabulary like `currency_code`), add the migration file to the `exclude:` list in `.pre-commit-config.yaml`:

```yaml
- id: sarj-ban-postgres-enums
  files: '^svcs/db/db/migrations/.*\.sql$'
  exclude: |
    (?x)^(
      svcs/db/db/migrations/20240101000000_create_currency_enum\.sql$
    )
```

Document the rationale in a comment near the exclude entry.

## References

- [Postgres docs — Enumerated Types](https://www.postgresql.org/docs/current/datatype-enum.html)
- [Postgres docs — `ALTER TYPE`](https://www.postgresql.org/docs/current/sql-altertype.html)
- [Brandur — "Native database enums in Postgres"](https://brandur.org/fragments/postgres-enums)
