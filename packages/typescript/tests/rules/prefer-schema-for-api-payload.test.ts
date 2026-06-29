import { RuleTester } from "@typescript-eslint/rule-tester";
import { afterAll, describe, it } from "vitest";

import rule from "../../src/rules/prefer-schema-for-api-payload.js";

RuleTester.afterAll = afterAll;
RuleTester.describe = describe;
RuleTester.it = it;
RuleTester.itOnly = it.only;

const ruleTester = new RuleTester();

ruleTester.run("prefer-schema-for-api-payload", rule, {
  valid: [
    // No json() involved.
    { code: "const x = { foo: 1 }; doStuff(x.foo);" },
    // Parsed through Zod.
    {
      code: "async function f(r) { const data = ZUser.parse(await r.json()); return data.name; }",
    },
    // safeParse.
    {
      code: "async function f(r) { const data = ZUser.safeParse(await r.json()); }",
    },
    // json() result used as opaque value, never field-accessed.
    {
      code: "async function f(r) { const data = await r.json(); return data; }",
    },
    // Direct `.parse()` chained off `.json()` is fine.
    {
      code: "async function f(r) { return ZUser.parse(await r.json()); }",
    },
    // Chained `.safeParse()` directly on the json() result is a validation.
    {
      code: "async function f(r) { return (await r.json()).safeParse(); }",
    },
    // Reassignment untracks: once `data` is reassigned to a parse result, later
    // field access is validated and must not be flagged.
    {
      code: "async function f(r) { let data = await r.json(); data = ZUser.parse(data); return data.name; }",
    },
  ],
  invalid: [
    {
      code: "async function f(r) { const data = await r.json(); return data.name; }",
      errors: [{ messageId: "unparsedJsonAccess" }],
    },
    {
      code: "async function f(r) { const payload = await r.json(); console.log(payload.id); }",
      errors: [{ messageId: "unparsedJsonAccess" }],
    },
    // Destructuring directly off a json() call.
    {
      code: "async function f(r) { const { name } = await r.json(); return name; }",
      errors: [{ messageId: "unparsedJsonAccess" }],
    },
    // Array-pattern destructuring directly off a json() call.
    {
      code: "async function f(r) { const [first] = await r.json(); return first; }",
      errors: [{ messageId: "unparsedJsonAccess" }],
    },
    // Array-pattern destructuring off a tracked variable.
    {
      code: "async function f(r) { const data = await r.json(); const [first] = data; return first; }",
      errors: [{ messageId: "unparsedJsonAccess" }],
    },
    // Direct field access on the json() result (no schema parse).
    {
      code: "async function f(r) { return (await r.json()).name; }",
      errors: [{ messageId: "unparsedJsonAccess" }],
    },
    // Post-first-access untracking: only the FIRST unvalidated read is flagged.
    {
      code: "async function f(r) { const d = await r.json(); console.log(d.a); console.log(d.b); }",
      errors: [{ messageId: "unparsedJsonAccess" }],
    },
  ],
});
