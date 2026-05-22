# `require-zod-form-validation`

> Reading from a `FormData` instance must flow through a Zod schema's `.parse()` or `.safeParse()` — never `.get()` directly into application code.

## What it catches

`formData.get("field")` (or `Object.fromEntries(formData)`) whose result is consumed by application code without first passing through a Zod schema.

## Why we encourage the alternative

`FormData.get()` returns `FormDataEntryValue | null` — i.e. `string | File | null`. The TypeScript type tells you nothing about whether the value is present, well-formed, or the right shape. In Next.js Server Actions and Remix actions, the form is the entry point of user input — the place where bugs cluster (XSS, validation bypass, missing required fields).

With Zod you describe the form schema once and get parsing + runtime validation + a `.SafeParseSuccess` result that's narrowed to the right TypeScript type for free:

```ts
const ZCheckout = z.object({
  email: z.string().email(),
  quantity: z.coerce.number().int().positive(),
});

export async function action(formData: FormData) {
  const parsed = ZCheckout.safeParse(Object.fromEntries(formData));
  if (!parsed.success) return { ok: false, errors: parsed.error.flatten() };
  // parsed.data is { email: string; quantity: number } — fully typed
}
```

## Bad

```ts
export async function action(formData: FormData) {
  const email = formData.get("email"); // string | File | null
  const quantity = Number(formData.get("quantity")); // NaN if missing
  await placeOrder({ email, quantity }); // runtime risk
}
```

## Good

```ts
const ZCheckout = z.object({
  email: z.string().email(),
  quantity: z.coerce.number().int().positive(),
});

export async function action(formData: FormData) {
  const parsed = ZCheckout.safeParse(Object.fromEntries(formData));
  if (!parsed.success) return { ok: false, errors: parsed.error.flatten() };
  await placeOrder(parsed.data);
  return { ok: true };
}
```

## More examples

**Multi-value fields** — use `formData.getAll()` only when the schema declares an array:

```ts
const ZSubscribe = z.object({
  email: z.string().email(),
  tags: z.array(z.string()),
});

// Good
const raw = {
  email: formData.get("email"),
  tags: formData.getAll("tags"),
};
const parsed = ZSubscribe.parse(raw);
```

**Coercion** — let Zod coerce strings to numbers/booleans/dates instead of hand-rolling:

```ts
// Bad
const qty = parseInt(formData.get("quantity") as string, 10);

// Good
const Z = z.object({ quantity: z.coerce.number().int() });
const { quantity } = Z.parse(Object.fromEntries(formData));
```

## When to suppress

For server actions that take a pre-parsed object (because some other layer already validated), or in tests where you're constructing the FormData yourself — disable per-line with a reason:

```ts
// eslint-disable-next-line @sarj/require-zod-form-validation -- mock form for unit test
const email = formData.get("email");
```

## References

- [Zod docs — coerce](https://zod.dev/?id=coercion-for-primitives)
- [Next.js docs — Server Actions and Mutations](https://nextjs.org/docs/app/building-your-application/data-fetching/server-actions-and-mutations)
