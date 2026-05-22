# `zod-naming-convention`

> Zod schemas must be named with a `Z` prefix so they're visually distinct from the inferred TypeScript types they generate.

## What it catches

`z.object(...)`, `z.string()`, `z.union(...)`, etc., assigned to a variable whose name doesn't start with `Z` followed by a capital letter.

The rule covers any module-level `const` initialized to a `z.*` call expression.

## Why we encourage the alternative

In a real codebase you typically generate two siblings from each schema:

```ts
const ZUser = z.object({ id: z.string(), name: z.string() });
type User = z.infer<typeof ZUser>;
```

If you also called the schema `User`, every call site has to disambiguate the value from the type at a glance — and you lose the ability to `import { ZUser }` for runtime validation while `import type { User }` for the type. The `Z` prefix gives you a single-letter signal: *uppercase Z = runtime schema, no prefix = TypeScript type.*

This is the same idea Brandon Roberts proposes in "Parse, don't validate" applied to TS: data crossing a boundary should be parsed (`ZUser.parse(...)`) into a type-safe value (`User`).

## Bad

```ts
import { z } from "zod";

const User = z.object({ id: z.string(), name: z.string() });
type UserDto = z.infer<typeof User>; // confusing: which one is the schema?
```

## Good

```ts
import { z } from "zod";

const ZUser = z.object({ id: z.string(), name: z.string() });
type User = z.infer<typeof ZUser>;
```

## More examples

**Discriminated unions** — every variant gets its own `Z`-prefixed schema:

```ts
// Good
const ZOrderPlaced = z.object({ kind: z.literal("placed"), at: z.date() });
const ZOrderShipped = z.object({ kind: z.literal("shipped"), at: z.date(), trackingId: z.string() });
const ZOrderEvent = z.discriminatedUnion("kind", [ZOrderPlaced, ZOrderShipped]);
type OrderEvent = z.infer<typeof ZOrderEvent>;
```

**Function arguments** — same rule applies inside a hook or component:

```ts
// Bad
function useOrder(input: unknown) {
  const orderSchema = z.object({ id: z.string() });
  return orderSchema.parse(input);
}

// Good
function useOrder(input: unknown) {
  const ZOrder = z.object({ id: z.string() });
  return ZOrder.parse(input);
}
```

## When to suppress

Almost never. If you're writing a one-off script that doesn't expose the schema outside the function, the rule still fires — disable per-line:

```ts
// eslint-disable-next-line @sarj/zod-naming-convention
const tmpSchema = z.object({ x: z.number() }).strict();
```

## References

- [Zod docs — type inference](https://zod.dev/?id=type-inference)
- ["Parse, don't validate" (Alexis King)](https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/)
