# `no-enum`

> Don't use TypeScript `enum`. Prefer a union of string literal types, or an `as const` object that yields the union via `typeof`.

## What it catches

Any `enum` declaration (`TSEnumDeclaration` AST node) — including `const enum`.

## Why we encourage the alternative

TypeScript `enum` is the language's only feature that emits runtime code by default. That has three downstream consequences:

1. **Bundle size** — every enum is compiled to a runtime object. Union types compile to nothing.
2. **Tree-shaking** — `const enum` was meant to fix this, but it breaks under `isolatedModules` (Vite, Next.js with Turbopack, esbuild). Most modern toolchains either disallow `const enum` or warn against it.
3. **Reverse mapping for numeric enums** — `MyEnum[0]` returns the string name, which is rarely what callers expect and silently widens the API.

A string-literal union or `as const` object gives you the same compile-time exhaustiveness, plays well with discriminated unions, and disappears at runtime.

## Bad

```ts
enum OrderStatus {
  Pending = "pending",
  Shipped = "shipped",
  Delivered = "delivered",
}

function describe(s: OrderStatus): string {
  switch (s) {
    case OrderStatus.Pending: return "On the way";
    /* ... */
  }
}
```

## Good — `as const` object

```ts
const ORDER_STATUS = {
  pending: "pending",
  shipped: "shipped",
  delivered: "delivered",
} as const;

type OrderStatus = typeof ORDER_STATUS[keyof typeof ORDER_STATUS];

function describe(s: OrderStatus): string {
  switch (s) {
    case "pending": return "On the way";
    /* ... */
  }
}
```

## Good — plain union

When you don't need a runtime lookup of valid values, just declare the union:

```ts
type OrderStatus = "pending" | "shipped" | "delivered";
```

## More examples

**Iterating valid values** — `as const` keeps an array around for free:

```ts
const ORDER_STATUSES = ["pending", "shipped", "delivered"] as const;
type OrderStatus = (typeof ORDER_STATUSES)[number];

for (const s of ORDER_STATUSES) {
  console.log(describe(s));
}
```

**Zod schema for the same values** — share a single source of truth:

```ts
const ZOrderStatus = z.enum(["pending", "shipped", "delivered"]);
type OrderStatus = z.infer<typeof ZOrderStatus>;
```

## When to suppress

If you depend on a third-party library that exports an `enum` and you're re-exporting it (rare), suppress at the re-export. Practically, you should almost never need this.

```ts
// eslint-disable-next-line @sarj/no-enum -- mirroring upstream `prisma.OrderStatus` enum
export { OrderStatus } from "@prisma/client";
```

## References

- [TypeScript handbook — enums](https://www.typescriptlang.org/docs/handbook/enums.html) (note the "objections" section)
- [Matt Pocock — "TypeScript enums considered harmful"](https://www.totaltypescript.com/why-i-dont-like-typescript-enums)
- [`isolatedModules` and `const enum`](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-0.html#all-enums-are-union-enums)
