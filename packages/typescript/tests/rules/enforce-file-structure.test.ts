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
    // A value const before a type — ordering among non-function declarations
    // is not enforced (stepdown: only function ordering matters).
    {
      filename: NON_ACTION_FILENAME,
      code: `
        const x = 1;
        type T = { a: number };
      `,
    },
    // Import after a type — both are declarations, not flagged.
    {
      filename: NON_ACTION_FILENAME,
      code: `
        type User = { name: string };
        import { z } from 'zod';
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
    // Type after a function
    {
      filename: NON_ACTION_FILENAME,
      code: `
        function foo() {}
        type User = { name: string };
      `,
      errors: [{ messageId: "incorrectOrder" }],
    },
    // Export then more functions then an import
    {
      filename: NON_ACTION_FILENAME,
      code: `
        export const x = 1;
        import { z } from 'zod';
      `,
      errors: [{ messageId: "incorrectOrder" }],
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
    // Constants after functions
    {
      filename: NON_ACTION_FILENAME,
      code: `
        function helper() {}
        const MAX = 5;
      `,
      errors: [{ messageId: "incorrectOrder" }],
    },
  ],
});
