import * as tsParser from "@typescript-eslint/parser";
import { RuleTester } from "@typescript-eslint/rule-tester";
import { afterAll, describe, it } from "vitest";

import rule from "../../src/rules/no-sequential-await.js";

RuleTester.afterAll = afterAll;
RuleTester.describe = describe;
RuleTester.it = it;
RuleTester.itOnly = it.only;

const ruleTester = new RuleTester({
  languageOptions: {
    parser: tsParser,
  },
});

ruleTester.run("no-sequential-await", rule, {
  valid: [
    // The prescribed pattern — concurrent awaits, no await inside the loop.
    {
      code: "async function f(xs) { await Promise.all(xs.map(async (x) => g(x))); }",
    },
    // `for await...of` is correct async iteration and must NOT be flagged.
    {
      code: "async function f(xs) { for await (const x of xs) { handle(x); } }",
    },
    // `for await...of` whose body also contains a (non-loop) await is still fine.
    {
      code: "async function f(xs) { for await (const x of xs) { await handle(x); } }",
    },
    // Await outside any loop.
    {
      code: "async function f() { const a = await one(); const b = await two(); }",
    },
    // Await inside a nested arrow defined within the loop — different scope.
    {
      code: "async function f(xs) { for (const x of xs) { ys.map(async (y) => await g(y)); } }",
    },
    // Await inside a nested function declaration within the loop — different scope.
    {
      code: "async function f(xs) { for (const x of xs) { async function inner() { await g(x); } inner(); } }",
    },
    // Await inside a nested function expression within the loop — different scope.
    {
      code: "async function f(xs) { while (xs.length) { const run = async function () { await g(); }; run(); } }",
    },
    // A loop with no await at all.
    {
      code: "function f(xs) { for (const x of xs) { use(x); } }",
    },
    // Await in a function whose body is reached after the loop closes.
    {
      code: "async function f(xs) { for (const x of xs) { use(x); } await done(); }",
    },
    // Promise.all built up over a loop without awaiting inside it.
    {
      code: "async function f(xs) { const ps = []; for (const x of xs) { ps.push(g(x)); } await Promise.all(ps); }",
    },
    // Nested loop owns the await — outer loop has no direct await of its own.
    // (The inner loop is the only thing flagged; see the invalid counterpart.)
    {
      code: "async function f(xs) { for (const x of xs) { if (x) { /* no await here */ ok(x); } } }",
    },
  ],
  invalid: [
    // for-of with a direct await.
    {
      code: "async function f(xs) { for (const x of xs) { await g(x); } }",
      errors: [{ messageId: "noSequentialAwait" }],
    },
    // C-style for with a direct await in the body.
    {
      code: "async function f(xs) { for (let i = 0; i < xs.length; i++) { await g(xs[i]); } }",
      errors: [{ messageId: "noSequentialAwait" }],
    },
    // for-in with a direct await.
    {
      code: "async function f(obj) { for (const k in obj) { await g(obj[k]); } }",
      errors: [{ messageId: "noSequentialAwait" }],
    },
    // while with a direct await.
    {
      code: "async function f(q) { while (q.length) { await g(q.pop()); } }",
      errors: [{ messageId: "noSequentialAwait" }],
    },
    // do-while with a direct await.
    {
      code: "async function f(q) { do { await g(q.pop()); } while (q.length); }",
      errors: [{ messageId: "noSequentialAwait" }],
    },
    // Await nested in a block / conditional but still directly in the loop scope.
    {
      code: "async function f(xs) { for (const x of xs) { if (x) { await g(x); } } }",
      errors: [{ messageId: "noSequentialAwait" }],
    },
    // Await in the loop's test/condition counts.
    {
      code: "async function f() { while (await next()) { use(); } }",
      errors: [{ messageId: "noSequentialAwait" }],
    },
    // Reported once per loop even with multiple awaits in one loop body.
    {
      code: "async function f(xs) { for (const x of xs) { await g(x); await h(x); } }",
      errors: [{ messageId: "noSequentialAwait" }],
    },
    // Two sibling loops each report independently.
    {
      code: "async function f(xs, ys) { for (const x of xs) { await g(x); } for (const y of ys) { await h(y); } }",
      errors: [
        { messageId: "noSequentialAwait" },
        { messageId: "noSequentialAwait" },
      ],
    },
    // Nested loops: only the inner loop owns its direct await, so exactly one
    // report — the outer loop has no await of its own.
    {
      code: "async function f(xs, ys) { for (const x of xs) { for (const y of ys) { await g(x, y); } } }",
      errors: [{ messageId: "noSequentialAwait" }],
    },
    // Nested loops where BOTH have a direct await — two reports.
    {
      code: "async function f(xs, ys) { for (const x of xs) { await pre(x); for (const y of ys) { await g(x, y); } } }",
      errors: [
        { messageId: "noSequentialAwait" },
        { messageId: "noSequentialAwait" },
      ],
    },
    // Await is the loop body itself (no block).
    {
      code: "async function f(xs) { for (const x of xs) await g(x); }",
      errors: [{ messageId: "noSequentialAwait" }],
    },
  ],
});
