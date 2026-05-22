# `prefer-server-actions`

> `fetch('/api/...', { method: 'POST'|'PUT'|'DELETE'|'PATCH' })` should be a Next.js Server Action. Hand-rolled `/api/*` route handlers belong to webhooks and external integrations, not internal mutations.

## What it catches

- `fetch(url, { method })` where `url` is a string literal or template literal starting with `/api/` AND the method (resolved from object shorthand or string literal) is a non-GET verb.
- `axios.post('/api/...')` / `.put` / `.delete` / `.patch` and the equivalent shapes on `ky` and named fetch wrappers (`api.post(...)`, `client.delete(...)`).

The rule deliberately doesn't flag `fetch('/api/users')` (default GET) — that pattern is fine for read endpoints behind cache headers.

## Why we encourage the alternative

Server Actions (Next.js App Router) are the modern replacement for hand-rolled API routes for *mutations triggered by the UI*:

| Concern | `/api/*` route + `fetch` | Server Action |
|---|---|---|
| End-to-end types | None (the route returns `unknown`, you Zod-parse the response) | `await placeOrder({ id })` returns the typed result |
| Boilerplate | Route file + JSON serialization + error envelope | One async function |
| `revalidatePath` / `revalidateTag` | Manual | First-class |
| Optimistic updates with `useFormState` | Manual | First-class |
| Streaming Suspense boundaries | Manual | First-class |
| CSRF | Manual | Built-in |

The `/api/*` pattern still has its place — webhooks (Stripe, Twilio, Clerk), public REST surfaces for non-RSC clients, server-to-server integrations. Those are unambiguous; the rule doesn't fire on the route handler itself, only on internal callers that should be Server Actions.

## Bad

```tsx
"use client";
async function archive(orderId: string) {
  const res = await fetch(`/api/orders/${orderId}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error("archive failed");
}
```

## Good

```tsx
// app/orders/actions.ts
"use server";

import { revalidatePath } from "next/cache";
import { db } from "@/db";

export async function archiveOrder(orderId: string) {
  await db.order.update({ where: { id: orderId }, data: { archivedAt: new Date() } });
  revalidatePath("/orders");
}
```

```tsx
// app/orders/page.tsx (consumer)
"use client";
import { archiveOrder } from "./actions";

function Row({ id }: { id: string }) {
  return <Button onClick={() => archiveOrder(id)}>Archive</Button>;
}
```

## More examples

**Dynamic URLs** — caught:

```tsx
// Bad
fetch(`/api/orders/${id}`, { method: "PUT", body: JSON.stringify(payload) });

// Good
await updateOrder(id, payload);
```

**Axios-style instance** — caught:

```ts
// Bad
await apiClient.post("/api/orders", payload);

// Good
await createOrder(payload);
```

**Webhook from Stripe** — *not* the target of this rule; the route handler is the right tool:

```ts
// app/api/webhooks/stripe/route.ts — fine
export async function POST(req: Request) {
  const evt = stripe.webhooks.constructEvent(...);
  // ...
}
```

## When to suppress

If you're calling your own public `/api/*` REST surface from a non-RSC client (mobile app, external integration), the route handler IS the API — suppress with a reason:

```tsx
// eslint-disable-next-line @sarj/prefer-server-actions -- React Native consumer hits the same public REST surface
await fetch(`${API_BASE}/api/orders`, { method: "POST", body: JSON.stringify(payload) });
```

## References

- [Next.js — Server Actions and Mutations](https://nextjs.org/docs/app/building-your-application/data-fetching/server-actions-and-mutations)
- [Next.js — `revalidatePath`](https://nextjs.org/docs/app/api-reference/functions/revalidatePath)
