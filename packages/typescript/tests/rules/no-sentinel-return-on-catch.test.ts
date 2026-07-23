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
    // \`return 0\` is often legitimate — not flagged.
    {
      code: `
        function f() {
          try { return run(); }
          catch (e) { return 0; }
        }
      `,
    },
    // \`return ""\` is often legitimate — not flagged.
    {
      code: `
        function f() {
          try { return run(); }
          catch (e) { return ""; }
        }
      `,
    },
    // Bare \`return;\` — out of scope for this rule.
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
    // Real site: error IS logged (console.error), \`[]\` is a degraded return.
    {
      code: `
        function fetchRows() {
          try { return query(); }
          catch (e) {
            console.error("query failed", e);
            return [];
          }
        }
      `,
    },
    // Real site: error reported to a central handler, \`undefined\` is the
    // declared \`T | undefined\` contract.
    {
      code: `
        function lookup(id) {
          try { return store.get(id); }
          catch (err) {
            onUnexpectedError(err);
            return undefined;
          }
        }
      `,
    },
    // Real site: logger receiver call before the sentinel return.
    {
      code: `
        function load() {
          try { return read(); }
          catch (e) {
            logger.warn("load failed", e);
            return null;
          }
        }
      `,
    },
    // Real site: safe-parse — \`undefined\` on bad input is the contract.
    {
      code: `
        function safeParse(x) {
          try { return JSON.parse(x); }
          catch { return undefined; }
        }
      `,
    },
    // Real site: \`new RegExp\` safe-construct — \`null\` on invalid pattern.
    {
      code: `
        function compile(pattern) {
          try { return new RegExp(pattern); }
          catch { return null; }
        }
      `,
    },
    // Real site: boolean predicate — a normal path also returns a boolean.
    {
      code: `
        function hasFeature(name) {
          if (!name) return false;
          try { return registry.check(name); }
          catch { return false; }
        }
      `,
    },
  ],
  invalid: [
    // return null — bare swallow, function otherwise returns real data.
    {
      code: `
        function f() {
          try { return run(); }
          catch (e) { return null; }
        }
      `,
      errors: [{ messageId: "noSentinelReturn" }],
    },
    // return undefined — no logging, no safe-parse contract.
    {
      code: `
        function f() {
          try { return run(); }
          catch (e) { return undefined; }
        }
      `,
      errors: [{ messageId: "noSentinelReturn" }],
    },
    // return false — no normal-path boolean, so not a predicate contract.
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
    // Non-logging work then a sentinel return still swallows the error.
    {
      code: `
        function f() {
          try { return run(); }
          catch (e) {
            cleanup();
            return [];
          }
        }
      `,
      errors: [{ messageId: "noSentinelReturn" }],
    },
    // A throw inside a NESTED function does not count as rethrow for this catch,
    // and register() neither logs nor reports the error.
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
