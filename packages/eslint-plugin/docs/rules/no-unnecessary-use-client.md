# `no-unnecessary-use-client`

> A file marked `'use client'` that doesn't actually use any client-side capability (hooks, event handlers, browser globals, client-only packages) can probably be a React Server Component.

## What it catches

A file whose first statement is the directive `"use client"` and which contains **none** of:

- A hook call (any function named `use*` — `useState`, `useEffect`, `useContext`, custom hooks).
- A JSX event-handler prop (`onClick`, `onChange`, …).
- A reference to a browser-only global (`window`, `document`, `localStorage`, `KeyboardEvent`, …).
- An import from a client-only library (`framer-motion`, `react-day-picker`, `@radix-ui/*`, `react-hook-form`, `@tanstack/react-query`, `next-themes`, etc. — see the maintained list in the rule source).
- A class declaration / class expression (often signals client-side state encapsulation).

`error.tsx` and `global-error.tsx` are exempted by filename — Next.js requires them to be client components even if they only render text.

## Why we encourage the alternative

The `'use client'` directive marks a component as a *client boundary*. Everything in the same module AND every component it imports gets pushed to the client bundle. Forgetting to remove it on a leaf component that has since become passive (only props in, only JSX out) silently inflates the bundle and sends server-renderable HTML through hydration unnecessarily.

Server Components:

- **Render on the server**, so the HTML is in the initial response (better TTFB, no client JS cost for that subtree).
- **Don't ship to the client**, so no JS bundle weight.
- **Can `async/await`** at the component level — no need for `useEffect` to load data.
- **Cannot use hooks or event handlers** — that's the boundary signal.

If a file marked `'use client'` doesn't use any of those client-only capabilities, it's paying the bundle cost for nothing.

## Bad

```tsx
"use client"; // <-- no hooks, no events, no browser globals → unnecessary

export function UserBadge({ name, role }: { name: string; role: string }) {
  return (
    <div className="badge">
      <span>{name}</span>
      <span className="text-muted">{role}</span>
    </div>
  );
}
```

## Good

```tsx
// no directive — this is a React Server Component
export function UserBadge({ name, role }: { name: string; role: string }) {
  return (
    <div className="badge">
      <span>{name}</span>
      <span className="text-muted">{role}</span>
    </div>
  );
}
```

## More examples

**Component imports a client-only library** — the rule does *not* fire (still need the directive):

```tsx
"use client";
import { AnimatePresence } from "framer-motion"; // client-only

export function FadeIn({ children }: { children: React.ReactNode }) {
  return <AnimatePresence>{children}</AnimatePresence>;
}
```

**Theme provider with context but no hooks** — uses `createContext`, which the rule's allowlist counts as a client indicator:

```tsx
"use client"; // OK — createContext is a client-side pattern
import { createContext } from "react";

export const ThemeCtx = createContext<"light" | "dark">("light");
```

**Class component for an error boundary** — the rule's class-declaration check covers this:

```tsx
"use client"; // OK — class-based error boundary
import React from "react";

export class ErrorBoundary extends React.Component { /* ... */ }
```

## When to suppress

False positives cluster around:

- **Side-effect-only client setup** that doesn't read hooks (rare). Suppress per-line:

```tsx
// eslint-disable-next-line @sarj/no-unnecessary-use-client -- triggers a polyfill load at module init
"use client";
import "core-js/proposals/array-from-async";
```

- **Files that re-export client components** without using any client API themselves. Add `"use client"` for the consumer's clarity and suppress.

This rule ships at `warn` in the `recommended` config because false positives are common at the edges. Promote to `error` once your codebase converges.

## References

- [Next.js — Client Components](https://nextjs.org/docs/app/building-your-application/rendering/client-components)
- [Next.js — Composition Patterns](https://nextjs.org/docs/app/building-your-application/rendering/composition-patterns)
