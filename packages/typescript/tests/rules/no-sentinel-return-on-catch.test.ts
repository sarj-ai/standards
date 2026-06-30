import * as tsParser from "@typescript-eslint/parser";
import { RuleTester } from "@typescript-eslint/rule-tester";
import { afterAll, describe, it } from "vitest";

import rule from "../../src/rules/no-sentinel-return-on-catch.js";

RuleTester.afterAll = afterAll;
RuleTester.describe = describe;
RuleTester.it = it;
RuleTester.itOnly = it.only;

const ruleTester = new RuleTester({
  languageOptions: {
    parser: tsParser,
  },
});

ruleTester.run("no-sentinel-return-on-catch", rule, {
  valid: [
    // Rethrow — the canonical correct handling.
    {
      code: `
        function f() {
          try { return run(); }
          catch (e) { throw e; }
        }
      `,
    },
    // Throws a wrapped error.
    {
      code: `
        function f() {
          try { return run(); }
          catch (e) { throw new Error("wrapped", { cause: e }); }
        }
      `,
    },
    // Throw appears before a later return — still rethrows, not swallowed.
    {
      code: `
        function f() {
          try { return run(); }
          catch (e) {
            if (isFatal(e)) throw e;
            return null;
          }
        }
      `,
    },
    // Returns a meaningful computed value (function call).
    {
      code: `
        function f() {
          try { return run(); }
          catch (e) { return fallback(e); }
        }
      `,
    },
    // Returns a meaningful variable.
    {
      code: `
        function f() {
          try { return run(); }
          catch (e) {
            const result = recover(e);
            return result;
          }
        }
      `,
    },
    // Returns a member expression — meaningful.
    {
      code: `
        function f() {
          try { return run(); }
          catch (e) { return defaults.value; }
        }
      `,
    },
    // Returns a non-empty array literal — meaningful.
    {
      code: `
        function f() {
          try { return run(); }
          catch (e) { return [fallbackItem]; }
        }
      `,
    },
    // Returns a non-empty object literal — meaningful.
    {
      code: `
        function f() {
          try { return run(); }
          catch (e) { return { ok: false, error: e }; }
        }
      `,
    },
    // `return 0` is often legitimate — not flagged.
    {
      code: `
        function f() {
          try { return run(); }
          catch (e) { return 0; }
        }
      `,
    },
    // `return ""` is often legitimate — not flagged.
    {
      code: `
        function f() {
          try { return run(); }
          catch (e) { return ""; }
        }
      `,
    },
    // Bare `return;` — out of scope for this rule.
    {
      code: `
        function f() {
          try { run(); }
          catch (e) { return; }
        }
      `,
    },
    // Sentinel return is NOT the final statement — conservative, not flagged.
    {
      code: `
        function f() {
          try { return run(); }
          catch (e) {
            if (cond) return null;
            return recover(e);
          }
        }
      `,
    },
    // Empty catch body — nothing returned, not flagged.
    {
      code: `
        function f() {
          try { run(); }
          catch (e) {}
        }
      `,
    },
    // Logs then rethrows — final statement is a throw, not a sentinel return.
    {
      code: `
        function f() {
          try { return run(); }
          catch (e) {
            log(e);
            throw e;
          }
        }
      `,
    },
  ],
  invalid: [
    // return null
    {
      code: `
        function f() {
          try { return run(); }
          catch (e) { return null; }
        }
      `,
      errors: [{ messageId: "noSentinelReturn" }],
    },
    // return undefined
    {
      code: `
        function f() {
          try { return run(); }
          catch (e) { return undefined; }
        }
      `,
      errors: [{ messageId: "noSentinelReturn" }],
    },
    // return false
    {
      code: `
        function f() {
          try { return run(); }
          catch (e) { return false; }
        }
      `,
      errors: [{ messageId: "noSentinelReturn" }],
    },
    // return [] — empty array, the classic idempotency-breaking swallow.
    {
      code: `
        function f() {
          try { return fetchRows(); }
          catch (e) { return []; }
        }
      `,
      errors: [{ messageId: "noSentinelReturn" }],
    },
    // return {} — empty object.
    {
      code: `
        function f() {
          try { return fetchMap(); }
          catch (e) { return {}; }
        }
      `,
      errors: [{ messageId: "noSentinelReturn" }],
    },
    // Sentinel return is the FINAL statement after other (non-throwing) work.
    {
      code: `
        function f() {
          try { return run(); }
          catch (e) {
            log(e);
            return [];
          }
        }
      `,
      errors: [{ messageId: "noSentinelReturn" }],
    },
    // A throw inside a NESTED function does not count as rethrow for this catch.
    {
      code: `
        function f() {
          try { return run(); }
          catch (e) {
            const onError = () => { throw e; };
            register(onError);
            return null;
          }
        }
      `,
      errors: [{ messageId: "noSentinelReturn" }],
    },
  ],
});
