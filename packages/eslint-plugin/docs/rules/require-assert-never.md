# `require-assert-never`

> A `switch` over a discriminated union must end with `assertNever(_)` in the default case so TypeScript fails to compile if you ever add a variant without handling it.

## What it catches

A `switch (expr)` whose default case (or fall-through end-of-cases) does not call `assertNever(...)` with the switched value.

## Why we encourage the alternative

Discriminated unions are how we encode finite state in TypeScript. Without `assertNever`, adding a new variant compiles fine — the new state silently hits the default branch at runtime. With `assertNever`, the compiler flags the unhandled case in CI before the code ever ships.

```ts
type Event =
  | { kind: "placed"; at: Date }
  | { kind: "shipped"; trackingId: string };

function handle(e: Event) {
  switch (e.kind) {
    case "placed":
      return queueFulfillment(e);
    case "shipped":
      return notifyCustomer(e);
    default:
      return assertNever(e); // <-- if we later add "cancelled", this won't compile
  }
}
```

`assertNever` is a one-line helper:

```ts
export function assertNever(x: never): never {
  throw new Error(`Unhandled case: ${JSON.stringify(x)}`);
}
```

## Bad

```ts
function handle(e: Event) {
  switch (e.kind) {
    case "placed":
      return queueFulfillment(e);
    case "shipped":
      return notifyCustomer(e);
    // missing default — adding a 3rd variant silently does nothing
  }
}
```

## Good

```ts
function handle(e: Event) {
  switch (e.kind) {
    case "placed":
      return queueFulfillment(e);
    case "shipped":
      return notifyCustomer(e);
    default:
      return assertNever(e);
  }
}
```

## More examples

**Returning vs throwing** — both are fine; the type system only requires the function returns `never`:

```ts
// Good — throws inside assertNever
default: assertNever(e);

// Also good — returns the result so the function can be typed as the variant return type
default: return assertNever(e);
```

**Nested unions** — apply the rule to every level:

```ts
function handle(e: Event) {
  switch (e.kind) {
    case "shipped":
      switch (e.carrier) {
        case "fedex": return notifyFedex(e);
        case "ups":   return notifyUps(e);
        default:      return assertNever(e); // <-- inner exhaustiveness
      }
    case "placed":
      return queueFulfillment(e);
    default:
      return assertNever(e); // <-- outer exhaustiveness
  }
}
```

## When to suppress

If the switched value is genuinely open-ended (`string`, `number`), `assertNever` doesn't compile — use `if/else` instead and disable the rule on that `switch`:

```ts
// eslint-disable-next-line @sarj/require-assert-never -- switched over user input, not a tagged union
switch (userTypedString) { ... }
```

## References

- [TypeScript docs — exhaustiveness checking](https://www.typescriptlang.org/docs/handbook/2/narrowing.html#exhaustiveness-checking)
- [Effective TS, item 27 — "Use exhaustiveness checking to limit cases"](https://effectivetypescript.com/)
