# @sarj/eslint-plugin

Custom ESLint rules for hypermodern TypeScript / React / Next.js projects.

## Install

```bash
pnpm add -D @sarj/eslint-plugin
# or: npm install --save-dev @sarj/eslint-plugin
```

## Usage (flat config)

```js
import sarj from "@sarj/eslint-plugin";

export default [
  {
    plugins: { "@sarj": sarj },
    rules: {
      // pick what you need, or use a config below
      "@sarj/no-client-side-data-fetching": "error",
      "@sarj/prefer-server-actions": "warn",
      "@sarj/no-unnecessary-use-client": "warn",
      "@sarj/prefer-schema-for-api-payload": "error",
    },
  },
];
```

Or use a preset:

```js
import sarj from "@sarj/eslint-plugin";

export default [
  // recommended: warn-first across most rules
  ...sarj.configs.recommended,
];
```

## Rules

Each rule links to its own docs page with bad/good examples, rationale, and suppression syntax.

### Foundations
| Rule | Description |
|---|---|
| [`@sarj/zod-naming-convention`](docs/rules/zod-naming-convention.md) | Zod schemas must be `Z<Name>` (e.g. `ZUser`). |
| [`@sarj/require-assert-never`](docs/rules/require-assert-never.md) | `switch` over discriminated union must end with `assertNever(_)`. |
| [`@sarj/require-zod-form-validation`](docs/rules/require-zod-form-validation.md) | `FormData` must be parsed through a Zod schema. |
| [`@sarj/enforce-file-structure`](docs/rules/enforce-file-structure.md) | Canonical top-of-file order: imports → types → constants → functions → exports. |
| [`@sarj/no-raw-env`](docs/rules/no-raw-env.md) | `process.env.*` must flow through a Zod-validated env module. |
| [`@sarj/prefer-shadcn`](docs/rules/prefer-shadcn.md) | Use shadcn/ui primitives instead of native HTML form elements. |
| [`@sarj/no-enum`](docs/rules/no-enum.md) | TypeScript `enum` is banned; use string literal unions or `as const`. |

### Next.js / RSC boundary (added in 1.1.0)
| Rule | Description |
|---|---|
| [`@sarj/no-client-side-data-fetching`](docs/rules/no-client-side-data-fetching.md) | No `fetch`/`axios` inside `useEffect`. Move to RSC / Server Action. |
| [`@sarj/prefer-server-actions`](docs/rules/prefer-server-actions.md) | `fetch('/api/*', { method: POST/PUT/DELETE })` should be a Server Action. |
| [`@sarj/no-unnecessary-use-client`](docs/rules/no-unnecessary-use-client.md) | `'use client'` files with no hooks / events can be RSC. |
| [`@sarj/prefer-schema-for-api-payload`](docs/rules/prefer-schema-for-api-payload.md) | `response.json()` must flow through a Zod schema parse. |

## Configs

- `recommended` — warn-first; foundations at error, RSC rules at warn.
- `strict` — every rule at error.
- `style-guide` — formatting/naming-only subset (legacy from sarj-eslint).
