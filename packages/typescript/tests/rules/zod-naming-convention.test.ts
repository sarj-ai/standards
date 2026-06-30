import { RuleTester } from "@typescript-eslint/rule-tester";
import { afterAll, describe, it } from "vitest";

import rule from "../../src/rules/zod-naming-convention.js";

// Bind vitest to RuleTester for proper test reporting
RuleTester.afterAll = afterAll;
RuleTester.describe = describe;
RuleTester.it = it;
RuleTester.itOnly = it.only;

const ruleTester = new RuleTester();

ruleTester.run("zod-naming-convention", rule, {
  valid: [
    // Direct z.object() with Z prefix
    { code: "const ZUser = z.object({ name: z.string() });" },
    // Chained z.object().extend() with Z prefix
    { code: "const ZUser = z.object({ name: z.string() }).extend({ age: z.number() });" },
    // Long chains with Z prefix
    {
      code: "const ZUser = z.object({ name: z.string() }).extend({ age: z.number() }).refine((d) => d.age > 0);",
    },
    // Non-Zod call expressions are ignored
    { code: "const user = createUser({ name: 'Alice' });" },
    // Non-CallExpression initializers are ignored
    { code: "const greeting = 'hello';" },
    // No initializer at all
    { code: "let unset;" },
    // z.literal — also Zod, with Z prefix
    { code: "const ZRole = z.literal('admin');" },
    // Member expression initializer that does not start with z
    { code: "const config = settings.values;" },
  ],
  invalid: [
    // Direct z.object() without Z prefix
    {
      code: "const User = z.object({ name: z.string() });",
      errors: [{ messageId: "zPrefix" }],
    },
    // Chained z.object().extend() without Z prefix
    {
      code: "const User = z.object({ name: z.string() }).extend({ age: z.number() });",
      errors: [{ messageId: "zPrefix" }],
    },
    // Lowercase z-prefixed name should still fail (must start with capital Z)
    {
      code: "const zUser = z.object({ name: z.string() });",
      errors: [{ messageId: "zPrefix" }],
    },
    // Even deeper chains still get flagged
    {
      code: "const User = z.object({}).extend({}).refine(() => true);",
      errors: [{ messageId: "zPrefix" }],
    },
    // z.enum() — schema, but wrong name
    {
      code: "const Role = z.enum(['admin', 'user']);",
      errors: [{ messageId: "zPrefix" }],
    },
  ],
});
