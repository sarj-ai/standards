# `prefer-schema-for-api-payload`

> Don't access fields on `await response.json()` without parsing it through a Zod (or equivalent) schema first.

## What it catches

The result of `await response.json()` (or `someClient.json()`) flowing into:

- `data.field` — direct member access
- `const { field } = data` — destructuring
- a function call whose argument is the raw `data`

…without first being passed to a schema's `.parse()` or `.safeParse()`. The rule uses ESLint's scope manager, so it correctly tracks variables across blocks and stops flagging once a variable is reassigned to a parsed value.

## Why we encourage the alternative

`response.json()` is typed `Promise<any>`. The moment a value flows into `any`, all TypeScript guarantees evaporate: you can call any method, read any property, pass it anywhere. The compiler will not save you when the upstream API quietly renames `customerId` to `customer_id` — but your runtime will (loudly, in production).

A schema parse at the boundary fixes this for free:

```ts
const ZUser = z.object({ id: z.string(), name: z.string(), email: z.string().email() });

async function getUser(id: string) {
  const res = await fetch(`/api/users/${id}`);
  const data = ZUser.parse(await res.json()); // throws if the upstream changed shape
  return data; // typed `{ id: string; name: string; email: string }`
}
```

Now if the API changes, you get a clear schema error at the call site instead of `Cannot read property 'name' of undefined` four layers deep.

## Bad

```ts
async function getUser(id: string) {
  const res = await fetch(`/api/users/${id}`);
  const data = await res.json();      // data is `any`
  return data.name as string;          // silent type lie
}
```

## Good — `parse` (throw on invalid)

```ts
import { z } from "zod";

const ZUser = z.object({ id: z.string(), name: z.string() });

async function getUser(id: string) {
  const res = await fetch(`/api/users/${id}`);
  const user = ZUser.parse(await res.json());
  return user.name;
}
```

## Good — `safeParse` (handle invalid)

```ts
async function getUser(id: string) {
  const res = await fetch(`/api/users/${id}`);
  const parsed = ZUser.safeParse(await res.json());
  if (!parsed.success) {
    log.warn({ issues: parsed.error.issues }, "user shape changed");
    return null;
  }
  return parsed.data.name;
}
```

## More examples

**Destructuring** — caught:

```ts
// Bad
const { name } = await res.json();

// Good
const { name } = ZUser.parse(await res.json());
```

**Direct chain** — caught:

```ts
// Bad
return (await res.json()).items[0];

// Good
return ZResponse.parse(await res.json()).items[0];
```

**Type assertion as parse substitute** — *not* enough, the rule still fires because there's no runtime validation:

```ts
// Bad — `as` is a lie, not a parse
const data = (await res.json()) as User;

// Good
const data = ZUser.parse(await res.json());
```

## When to suppress

Genuinely untyped responses (debug endpoints, third-party APIs you've decided to consume raw) — suppress with a reason explaining the trust boundary:

```ts
// eslint-disable-next-line @sarj/prefer-schema-for-api-payload -- internal /api/_debug endpoint, no schema worth maintaining
const debug = await res.json();
console.log(debug);
```

## References

- [Zod docs — `parse` / `safeParse`](https://zod.dev/?id=parse)
- [Matt Pocock — "Parse, don't validate"](https://www.totaltypescript.com/parse-don-t-validate)
- [Alexis King — "Parse, don't validate"](https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/)
