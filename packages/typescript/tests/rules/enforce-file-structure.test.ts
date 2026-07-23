import { RuleTester } from "@typescript-eslint/rule-tester";
import { afterAll, describe, it } from "vitest";

import rule from "../../src/rules/enforce-file-structure.js";

// Bind vitest to RuleTester for proper test reporting
RuleTester.afterAll = afterAll;
RuleTester.describe = describe;
RuleTester.it = it;
RuleTester.itOnly = it.only;

const ruleTester = new RuleTester();

// Non-action filename — avoid triggering the use-server check by default.
// `<input>` is the default filename used by RuleTester when none is supplied;
// it doesn't include "action" or "/actions/", so the use-server check stays
// out of the way for ordering-focused fixtures.
const NON_ACTION_FILENAME = "src/components/some-component.ts";
const ACTION_FILENAME = "src/actions/create-user.ts";

ruleTester.run("enforce-file-structure", rule, {
  valid: [
    // Canonical ordering: imports → types → constants → functions → exports
    {
      filename: NON_ACTION_FILENAME,
      code: `
        import { z } from 'zod';
        type User = { name: string };
        const MAX_USERS = 10;
        function makeUser(name: string) { return { name }; }
        export { makeUser };
      `,
    },
    // Only imports
    {
      filename: NON_ACTION_FILENAME,
      code: `import { z } from 'zod';`,
    },
    // Functions then exports — no earlier sections
    {
      filename: NON_ACTION_FILENAME,
      code: `
        function add(a: number, b: number) { return a + b; }
        export { add };
      `,
    },
    // Server action file with 'use server' at top
    {
      filename: ACTION_FILENAME,
      code: `
        'use server';
        import { z } from 'zod';
        export async function createUser() {}
      `,
    },
    // Multiple imports in a row
    {
      filename: NON_ACTION_FILENAME,
      code: `
        import { z } from 'zod';
        import { useState } from 'react';
        export const x = 1;
      `,
    },
    // Constants before functions
    {
      filename: NON_ACTION_FILENAME,
      code: `
        const MAX = 5;
        const helper = () => 1;
      `,
    },
    // A value const before a type — ordering among body statements is not
    // enforced (step-down: only imports-first is required).
    {
      filename: NON_ACTION_FILENAME,
      code: `
        const x = 1;
        type T = { a: number };
      `,
    },
    // Step-down: a public exported function followed by a private helper
    // function must NOT fire — this is the dominant TS layout. Mirrors the
    // VS Code false-positive site (13k hits): `pauseCSSAnimationsWhenHidden`
    // exported, `disposeVisibilityObserverIfEmpty` a private helper below it.
    {
      filename: NON_ACTION_FILENAME,
      code: `
        export function pauseCSSAnimationsWhenHidden() {
          return disposeVisibilityObserverIfEmpty();
        }
        function disposeVisibilityObserverIfEmpty() { return true; }
      `,
    },
    // Step-down with a private *value* helper below the public function — an
    // exported function is a function, the const below it is a declaration,
    // and both share the same body, so ordering between them is free.
    {
      filename: NON_ACTION_FILENAME,
      code: `
        export function render() { return TEMPLATE; }
        const TEMPLATE = '<div></div>';
      `,
    },
    // An exported interface among declarations must NOT fire: an exported
    // interface IS a declaration, so a private const below it is fine.
    {
      filename: NON_ACTION_FILENAME,
      code: `
        export interface VisibilityState { hidden: boolean }
        const DEFAULT_STATE = { hidden: false };
      `,
    },
    // Exported declaration followed by a private helper function — the
    // exported `type`/`enum`/`class` are declarations, not terminal exports.
    {
      filename: NON_ACTION_FILENAME,
      code: `
        export type Point = { x: number; y: number };
        export enum Axis { X, Y }
        function origin(): Point { return { x: 0, y: 0 }; }
      `,
    },
    // Generated `_namespaces` re-export barrel: interleaved `import * as X` /
    // `export { X }`. Re-exports are neutral, so this passes.
    {
      filename: "src/_namespaces/ts.ts",
      code: `
        import * as ts from '../ts';
        export { ts };
        import * as server from '../server';
        export { server };
      `,
    },
    // Pure re-export barrel with `export * from` / `export { … } from`.
    {
      filename: "src/index.ts",
      code: `
        export * from './parser';
        export { scan } from './scanner';
        export { emit } from './emitter';
      `,
    },
    // `transaction.ts` is NOT a server action (substring "action" must not match).
    {
      filename: "src/lib/transaction.ts",
      code: `
        const TAX_RATE = 0.2;
        type Transaction = { amount: number };
        export function total(t: Transaction) { return t.amount * (1 + TAX_RATE); }
      `,
    },
    // `redaction.ts` is NOT a server action either.
    {
      filename: "src/lib/redaction.ts",
      code: `export function redact(s: string) { return s; }`,
    },
  ],
  invalid: [
    // Import after a body statement (an exported const) — imports must be first.
    {
      filename: NON_ACTION_FILENAME,
      code: `
        export const x = 1;
        import { z } from 'zod';
      `,
      errors: [{ messageId: "importsFirst" }],
    },
    // Import after a type declaration — still imports-first.
    {
      filename: NON_ACTION_FILENAME,
      code: `
        type User = { name: string };
        import { z } from 'zod';
      `,
      errors: [{ messageId: "importsFirst" }],
    },
    // Import after a function — imports-first.
    {
      filename: NON_ACTION_FILENAME,
      code: `
        function foo() {}
        import { z } from 'zod';
      `,
      errors: [{ messageId: "importsFirst" }],
    },
    // Server action file missing 'use server'
    {
      filename: ACTION_FILENAME,
      code: `
        import { z } from 'zod';
        export async function createUser() {}
      `,
      errors: [{ messageId: "useServerDirective" }],
    },
  ],
});
