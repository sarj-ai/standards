import { RuleTester } from "@typescript-eslint/rule-tester";
import { afterAll, describe, it } from "vitest";

import rule from "../../src/rules/require-zod-form-validation.js";

// Bind vitest to RuleTester for proper test reporting
RuleTester.afterAll = afterAll;
RuleTester.describe = describe;
RuleTester.it = it;
RuleTester.itOnly = it.only;

const ruleTester = new RuleTester();

ruleTester.run("require-zod-form-validation", rule, {
  valid: [
    // formData.get() wrapped in a Zod schema .parse() call
    {
      code: "const name = ZUser.parse({ name: formData.get('name') });",
    },
    // safeParse is a valid Zod validation too (regression: previously rejected).
    {
      code: "const name = ZUser.safeParse({ name: formData.get('name') });",
    },
    // Schema-suffixed receiver counts as a Zod schema.
    {
      code: "const name = userSchema.parse({ name: formData.get('name') });",
    },
    // `z.*` builder chain counts as a Zod schema.
    {
      code: "const name = z.object({ name: z.string() }).parse({ name: formData.get('name') });",
    },
    // Nested: .parse() ancestor exists somewhere above
    {
      code: "const result = ZUser.parse({ inner: { name: formData.get('name') } });",
    },
    // Reading from a different identifier that isn't a form source
    {
      code: "const name = req.body.get('name');",
    },
    // Non-`.get()` member call on formData — rule only targets `.get(...)`
    {
      code: "for (const key of formData.keys()) {}",
    },
    // .parse() ancestor at the top level expression
    {
      code: "ZForm.parse(Object.fromEntries([['name', formData.get('name')]]));",
    },
    // Un-hardcoded receiver: a binding from `.formData()`, validated via Zod.
    {
      code: "async function f(req) { const fd = await req.formData(); return ZUser.parse({ name: fd.get('name') }); }",
    },
  ],
  invalid: [
    // Bare formData.get() with no Zod validation
    {
      code: "const name = formData.get('name');",
      errors: [{ messageId: "missingZodValidation" }],
    },
    // formData.get() inside an unrelated function call
    {
      code: "console.log(formData.get('name'));",
      errors: [{ messageId: "missingZodValidation" }],
    },
    // JSON.parse is NOT Zod validation — must still be flagged (false-negative fix).
    {
      code: "const name = JSON.parse(formData.get('name'));",
      errors: [{ messageId: "missingZodValidation" }],
    },
    // Date.parse is NOT Zod validation either.
    {
      code: "const ts = Date.parse(formData.get('createdAt'));",
      errors: [{ messageId: "missingZodValidation" }],
    },
    // Un-hardcoded receiver: a binding from `.formData()` with no validation.
    {
      code: "async function f(req) { const fd = await req.formData(); return fd.get('name'); }",
      errors: [{ messageId: "missingZodValidation" }],
    },
    // Multiple unvalidated reads — each is flagged
    {
      code: "const a = formData.get('a'); const b = formData.get('b');",
      errors: [
        { messageId: "missingZodValidation" },
        { messageId: "missingZodValidation" },
      ],
    },
  ],
});
