# @sarj/eslint-plugin

Custom ESLint rules for hypermodern TypeScript / React / Next.js projects.

```bash
pnpm add -D @sarj/eslint-plugin
```

```js
// eslint.config.mjs
import sarj from "@sarj/eslint-plugin";
export default [...sarj.configs.recommended];
```

Each rule's source under `lib/rules/` carries its own `meta.docs.description` + `meta.messages` — read the file for full rationale.

Presets: `recommended` (warn-first), `strict` (every rule at error), `style-guide` (formatting/naming subset).
