# `no-raw-env`

> Never read `process.env.*` directly. All environment variables must flow through a Zod-validated env module so they're typed, validated at boot, and discoverable.

## What it catches

Any `MemberExpression` of the form `process.env.<NAME>` outside of the canonical env-loader module(s).

## Why we encourage the alternative

`process.env.X` returns `string | undefined`. Every consumer has to remember to check for undefined, coerce types, and handle invalid values. That logic gets duplicated and drifts. A single Zod-validated env module solves all of those at once:

```ts
// env.ts
import { z } from "zod";

const ZEnv = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]),
  DATABASE_URL: z.string().url(),
  PORT: z.coerce.number().int().positive().default(3000),
  STRIPE_SECRET_KEY: z.string().min(1),
});

export const env = ZEnv.parse(process.env);
```

Now everywhere else in the codebase:

```ts
import { env } from "@/env";

// env.PORT is `number` (typed + validated at boot)
const server = createServer().listen(env.PORT);
```

If `STRIPE_SECRET_KEY` is missing in prod, the app fails to boot loudly instead of misbehaving silently three hours later when the first checkout fires.

## Bad

```ts
const port = parseInt(process.env.PORT || "3000", 10);
const stripeKey = process.env.STRIPE_SECRET_KEY!; // non-null assertion + no validation
```

## Good

```ts
import { env } from "@/env";

const port = env.PORT;          // typed number
const stripeKey = env.STRIPE_SECRET_KEY; // typed string, guaranteed present
```

## More examples

**Feature flags** — also flow through the env schema:

```ts
const ZEnv = z.object({
  FEATURE_NEW_CHECKOUT: z.coerce.boolean().default(false),
});
```

**Computed values** — derive them once in the env module, not at every call site:

```ts
const ZRawEnv = z.object({ DATABASE_URL: z.string().url() });
const raw = ZRawEnv.parse(process.env);

export const env = {
  ...raw,
  isProd: raw.NODE_ENV === "production",
};
```

## When to suppress

Three legitimate sites:

1. **Inside `env.ts` itself** — that's where validation happens, by construction it must touch `process.env`.
2. **Build configs** (`next.config.ts`, `vite.config.ts`) that run before the env module loads.
3. **A chicken-and-egg bootstrap** (a process manager that has to set `process.env.PYTHONHASHSEED` before importing anything).

```ts
// next.config.ts
// eslint-disable-next-line @sarj/no-raw-env -- build-time, runs before env.ts loads
const isAnalyze = process.env.ANALYZE === "true";
```

## References

- [Zod docs — `safeParse`](https://zod.dev/?id=safeparse)
- [12-Factor App — config](https://12factor.net/config)
- [T3 Stack `@t3-oss/env-nextjs`](https://env.t3.gg/)
