# `sarj-require-if-not-exists-on-create`

> Every `CREATE TABLE` in a migration must use `IF NOT EXISTS`. Migrations must be safe to re-run.

## What it catches

A regex match for `(?i)CREATE TABLE(?! IF NOT EXISTS)` in any file matching the consumer's `files:` glob.

## Why we encourage the alternative

Migrations get run more than once. Concretely:

- **Partial failure.** A migration step succeeds at `CREATE TABLE` but fails at the next `CREATE INDEX`. Without `IF NOT EXISTS`, the rerun fails immediately on the table create — and you can't tell whether the table is the "old" one (safe to drop) or a half-finished new one (data risk).
- **Multi-environment drift.** Local dev, staging, prod — sometimes a manual hotfix creates an object out of band. The next migration that "creates" that object will fail without `IF NOT EXISTS`.
- **CI re-runs.** Test runners that share a database across test runs need DDL to be safely re-runnable.
- **Disaster recovery.** Restoring from a partial backup and replaying migrations needs idempotent DDL.

`CREATE TABLE IF NOT EXISTS` is a one-token change that makes the migration robust to all of the above. The trade-off is small: if the table exists with a *different* schema, you get a silent no-op instead of a loud failure — which is why you should pair this with schema drift detection (a `dbmate diff`, `migra`, or `atlas` step in CI).

The same logic applies to `CREATE INDEX`, `ADD COLUMN`, `CREATE SEQUENCE`, `CREATE FUNCTION` — every DDL operation has an `IF NOT EXISTS` / `OR REPLACE` form. This rule only covers `CREATE TABLE`; you should adopt the same discipline for the others.

## Bad

```sql
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    placed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## Good

```sql
CREATE TABLE IF NOT EXISTS orders (
    id BIGSERIAL PRIMARY KEY,
    placed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## More examples

**Partitioned tables**:

```sql
-- Good
CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL,
    ts TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL
) PARTITION BY RANGE (ts);

CREATE TABLE IF NOT EXISTS events_2026_05 PARTITION OF events
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
```

**Indexes** — same discipline (not covered by this rule but recommended):

```sql
-- Good
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders (user_id);
```

**Unique constraints / extensions** — same:

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email ON users (email);
```

## When to suppress

Migrations that intentionally fail on rerun (e.g. a one-shot data migration that should never repeat). Exclude the specific file:

```yaml
- id: sarj-require-if-not-exists-on-create
  files: '^svcs/db/db/migrations/.*\.sql$'
  exclude: |
    (?x)^(
      svcs/db/db/migrations/20240715_one_shot_backfill\.sql$
    )
```

Better: structure one-shot data backfills so the *operation* (UPDATE / INSERT) is idempotent (`ON CONFLICT DO NOTHING`, `WHERE ... IS NULL`), and keep all DDL safely re-runnable.

## References

- [Postgres docs — `CREATE TABLE` (`IF NOT EXISTS`)](https://www.postgresql.org/docs/current/sql-createtable.html)
- [`dbmate` migration tool](https://github.com/amacneil/dbmate)
- [Strong Migrations — safe Rails migration patterns (concepts apply to any DB)](https://github.com/ankane/strong_migrations)
