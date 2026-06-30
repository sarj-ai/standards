/**
 * @fileoverview Shared helpers for the Tailwind-className rules. className values
 * are reachable as plain string `Literal`s (attribute values, `cn()`/`clsx()`/
 * `cva()`/`tv()` args, and className-holding constants) and as the static quasis of
 * `TemplateLiteral`s — so the rules visit both node types and run these helpers.
 */

/**
 * Strip Tailwind variant prefixes (`hover:`, `dark:`, `focus-visible:`, …) and a
 * leading `!` important marker, leaving the bare utility (`bg-red-500`). Variants are
 * `[a-z0-9-]+:` runs at the start; bracketed arbitrary values never start a token, so
 * a `:` inside `[url(http://…)]` is not mistaken for a variant separator.
 */
export const tailwindBase = (token: string): string =>
  token.replace(/^(?:[a-z0-9-]+:)+/i, "").replace(/^!/, "");

/** Split a className string into its non-empty class tokens. */
export const classTokens = (value: string): readonly string[] =>
  value.split(/\s+/).filter(Boolean);
