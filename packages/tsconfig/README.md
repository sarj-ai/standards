# @sarj/tsconfig

Hyper-modern, maximally-strict TypeScript configs for sarj-ai projects.
Audited against bulbul's production tsconfigs + community presets (`@tsconfig/strictest`, `@total-typescript/tsconfig`, `sindresorhus/tsconfig`).

Strictly a superset of every flag in bulbul's `tsconfig.base.json` and `integration-client/tsconfig.json`.

## Install

```bash
npm i -D @sarj/tsconfig typescript
# or
yarn add -D @sarj/tsconfig typescript
```

## Use

`tsconfig.json` — the default for new projects:

```json
{
  "extends": "@sarj/tsconfig/strict.json",
  "include": ["src/**/*"]
}
```

For libraries that need to be less strict (e.g. mid-migration), extend the base:

```json
{
  "extends": "@sarj/tsconfig/base.json"
}
```

## What's enabled

### `base.json` — modern defaults + bulbul-parity strict-safety

**Module / target (TS 6 + Node 24 LTS):**

- `target: "ES2025"` / `lib: ["ES2025"]` — Iterator helpers, `Promise.try`, Set methods, `RegExp.escape`, Float16Array
- `module: "NodeNext"` / `moduleResolution: "NodeNext"` — Node 24 native ESM resolution
- `moduleDetection: "force"` — every file is a module; no accidental global scripts
- `verbatimModuleSyntax: true` — `import type` required for type-only imports
- `isolatedModules: true` — every file is a standalone compilation unit
- `allowJs: false` — TS-only; no `.js` infiltration
- `esModuleInterop` / `allowSyntheticDefaultImports`
- `resolveJsonModule: true`

**Type-safety hygiene (matches bulbul base):**

- `strict: true`
- `noUncheckedIndexedAccess: true` — `arr[0]` is `T | undefined`
- `noUncheckedSideEffectImports: true` (TS 5.6+)
- `exactOptionalPropertyTypes: true`
- `noImplicitOverride: true`
- `noImplicitReturns: true`
- `noFallthroughCasesInSwitch: true`
- `noPropertyAccessFromIndexSignature: true` — bracket only for index signatures
- `noUnusedLocals: true` / `noUnusedParameters: true`
- `allowUnreachableCode: false` / `allowUnusedLabels: false`
- `useDefineForClassFields: true`

**Emit / publish:**

- `declaration: true` / `declarationMap: true` / `sourceMap: true`
- `newLine: "lf"` — reproducible cross-platform output
- `stripInternal: true` — `@internal`-tagged declarations don't ship
- `forceConsistentCasingInFileNames: true`
- `skipLibCheck: true`

**Misc:**

- `ignoreDeprecations: "6.0"` — silences TS 6.0 `baseUrl` warnings emitted by tools like tsup

### `strict.json` — extends base + the hyper-strict flags

- `isolatedDeclarations: true` (TS 5.5+) — forces explicit return types on every exported symbol; enables parallel `.d.ts` emit by `tsgo`/`swc`/`oxc`
- `erasableSyntaxOnly: true` (TS 5.8+) — bans non-erasable syntax (enums, namespaces with values, parameter properties, `import =`); pairs with Node 24's `--experimental-strip-types`
- `noErrorTruncation: true` — full type names in errors, no `...`
- `strictBuiltinIteratorReturn: true` (TS 5.6+) — plugs the `any` leak in built-in iterators
- All strict-family sub-flags explicitly listed (`alwaysStrict`, `noImplicitAny`, `noImplicitThis`, `strictBindCallApply`, `strictFunctionTypes`, `strictNullChecks`, `strictPropertyInitialization`, `useUnknownInCatchVariables`) — redundant with `strict: true` from base but pinned so future TS default flips can't loosen them

## What's NOT in the preset (and why)

These were considered and explicitly rejected — they're per-project decisions, not shared-config concerns:

| Flag | Why not in @sarj/tsconfig |
|------|---------------------------|
| `composite` / `incremental` | Per-project; depends on whether you use project references |
| `noEmit` | App-vs-lib; apps want `true`, libs want `false` |
| `outDir` / `rootDir` / `paths` / `include` / `exclude` | Per-project layout |
| `jsx` | Framework-specific (`preserve` for Next, `react-jsx` for plain React) |
| `DOM` / `DOM.Iterable` in `lib` | Base is Node-safe; browser packages add DOM in their own tsconfig |
| `types` / `typeRoots` | Forces every consumer to enumerate ambient types — high friction |
| `noEmitOnError` | Breaks dev/editor partial-emit workflows; gate via separate `tsc --noEmit` in CI |
| `rewriteRelativeImportExtensions` / `allowImportingTsExtensions` | Per-runtime decision (depends on whether you run `.ts` directly) |

## Versioning

Semver. Major-bump on TypeScript major releases (currently TS 6.x).

## Provenance

These configs were authored via a 10-agent hyper-strict audit comparing the draft against:

- bulbul's `tsconfig.base.json` (the Next.js + lib monorepo baseline)
- bulbul's `integration-client/tsconfig.json` (the published SDK strict reference)
- `@tsconfig/strictest`, `@total-typescript/tsconfig`, `sindresorhus/tsconfig`, `@swan-io/tsconfig`, `vercel/style-guide`
- TypeScript handbook strict-mode reference
- Every strict-related flag introduced from TS 5.0 → 6.0
