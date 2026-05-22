# `prefer-shadcn`

> Use shadcn/ui primitives instead of native HTML form elements so the design system stays consistent and accessibility/styling is centralized.

## What it catches

Direct use of `<button>`, `<input>`, `<select>`, `<textarea>`, `<dialog>`, `<table>` (and a handful of related elements) in JSX, when the corresponding shadcn/ui component exists in `@/components/ui/*`.

## Why we encourage the alternative

shadcn/ui components have:

- **Consistent design tokens** — colors, radius, spacing, focus rings all flow from the same theme.
- **Built-in accessibility** — proper ARIA roles, keyboard handling, focus management.
- **Variants** that compose with Tailwind (`<Button variant="ghost" size="sm">`) — you don't reinvent the same `bg-primary text-primary-foreground px-3 py-1 rounded-md...` chain in every file.
- **A single point of upgrade** — when the design system shifts, you patch `components/ui/button.tsx` and every consumer follows.

Rolling your own `<button>` in a new feature file is how a design system rots: each click target ends up looking slightly different, and the team eventually pays for the cleanup.

## Bad

```tsx
function OrderRow({ order }: { order: Order }) {
  return (
    <div className="border p-4">
      <button
        className="bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded"
        onClick={() => archive(order.id)}
      >
        Archive
      </button>
    </div>
  );
}
```

## Good

```tsx
import { Button } from "@/components/ui/button";

function OrderRow({ order }: { order: Order }) {
  return (
    <div className="border p-4">
      <Button variant="secondary" size="sm" onClick={() => archive(order.id)}>
        Archive
      </Button>
    </div>
  );
}
```

## More examples

**Form input** — use `<Input>`:

```tsx
// Bad
<input type="text" className="..." />

// Good
import { Input } from "@/components/ui/input";
<Input type="text" placeholder="Search…" />
```

**Modal** — use `<Dialog>`:

```tsx
// Bad — native <dialog> needs polyfills + manual focus trap
<dialog open>...</dialog>

// Good
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
<Dialog>
  <DialogTrigger asChild><Button>Open</Button></DialogTrigger>
  <DialogContent>...</DialogContent>
</Dialog>
```

## When to suppress

Marketing-only pages or generated content where the design system doesn't apply (e.g. an embedded `<table>` from a CMS render). Suppress per-line with a reason:

```tsx
{/* eslint-disable-next-line @sarj/prefer-shadcn -- rendered HTML from CMS */}
<table dangerouslySetInnerHTML={{ __html: post.tableHtml }} />
```

## References

- [shadcn/ui docs](https://ui.shadcn.com/)
- [Radix UI — accessibility primitives](https://www.radix-ui.com/primitives)
