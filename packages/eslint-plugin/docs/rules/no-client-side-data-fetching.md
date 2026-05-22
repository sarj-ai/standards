# `no-client-side-data-fetching`

> Don't `fetch` / `axios` inside `useEffect`. Move data fetching to a React Server Component, a Server Action, or a client-side cache library (SWR, React Query).

## What it catches

A `fetch(...)`, `axios.get(...)`, `ky.get(...)`, or `superagent.get(...)` call inside the body of a `useEffect` / `React.useEffect`. Non-GET requests (POST/PUT/DELETE/PATCH) and URLs containing analytics keywords (`analytics`, `telemetry`, `track`, `log`, `ping`, `beacon`, `metrics`) are excluded — those are legitimate side-effects, not data loading.

## Why we encourage the alternative

`useEffect(() => fetch(...).then(setData), [])` is the canonical "I'm new to React" pattern, and it's almost always wrong in 2026:

1. **Waterfall** — the component renders empty, mounts, *then* requests data; the user sees a loading state for one extra network round-trip.
2. **No cache** — every navigation that mounts the component refetches. Background revalidation, stale-while-revalidate, and request deduping are all on you.
3. **Layout shift** — the empty render → data render flip pushes content around.
4. **No streaming** — Server Components let the framework stream HTML as data resolves, eliminating the empty state entirely.

The right replacement depends on context:

| Use case | Replacement |
|---|---|
| Server-rendered page data | React Server Component (`async function Page()`) |
| Mutation triggered by a form | Server Action |
| Client cache with revalidation | TanStack Query / SWR |
| Real-time updates | WebSocket / Server-Sent Events / RSC streaming |

## Bad

```tsx
"use client";
import { useEffect, useState } from "react";

export function UserCard({ id }: { id: string }) {
  const [user, setUser] = useState<User | null>(null);
  useEffect(() => {
    fetch(`/api/users/${id}`)
      .then((r) => r.json())
      .then(setUser);
  }, [id]);
  if (!user) return <Skeleton />;
  return <Card>{user.name}</Card>;
}
```

## Good — React Server Component

```tsx
// app/users/[id]/page.tsx — no 'use client' directive
async function Page({ params }: { params: { id: string } }) {
  const user = await getUser(params.id); // runs on the server, streamed to the client
  return <Card>{user.name}</Card>;
}
```

## Good — TanStack Query (when client interaction is required)

```tsx
"use client";
import { useQuery } from "@tanstack/react-query";

export function UserCard({ id }: { id: string }) {
  const { data: user } = useQuery({
    queryKey: ["user", id],
    queryFn: () => fetch(`/api/users/${id}`).then((r) => r.json()),
  });
  if (!user) return <Skeleton />;
  return <Card>{user.name}</Card>;
}
```

## More examples

**axios** — same rule, same fix:

```tsx
// Bad
useEffect(() => {
  axios.get(`/api/users/${id}`).then((r) => setUser(r.data));
}, [id]);
```

**Analytics ping** — *not* flagged (URL contains `track`):

```tsx
useEffect(() => {
  fetch(`/analytics/track?event=view&id=${id}`, { method: "POST" });
}, [id]);
```

**Custom fetch wrapper** — the rule is intentionally conservative; if your wrapper is called something like `api.fetchUser(id)` the rule won't catch it. Either rename to make the side-effect obvious or rely on review.

## When to suppress

Real-time streams, polling, or one-off integrations that genuinely need an effect. Always pair with a reason:

```tsx
useEffect(() => {
  // eslint-disable-next-line @sarj/no-client-side-data-fetching -- intentional 1Hz poll, no SSE available
  const id = setInterval(() => fetch("/api/heartbeat").then(...), 1000);
  return () => clearInterval(id);
}, []);
```

## References

- [React docs — "You might not need an Effect"](https://react.dev/learn/you-might-not-need-an-effect)
- [Next.js — Data Fetching](https://nextjs.org/docs/app/building-your-application/data-fetching)
- [TanStack Query](https://tanstack.com/query)
