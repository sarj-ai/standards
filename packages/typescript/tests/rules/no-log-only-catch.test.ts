import * as tsParser from "@typescript-eslint/parser";
import { RuleTester } from "@typescript-eslint/rule-tester";
import { afterAll, describe, it } from "vitest";

import rule from "../../src/rules/no-log-only-catch.js";

RuleTester.afterAll = afterAll;
RuleTester.describe = describe;
RuleTester.it = it;
RuleTester.itOnly = it.only;

const ruleTester = new RuleTester({
  languageOptions: {
    parser: tsParser,
  },
});

ruleTester.run("no-log-only-catch", rule, {
  valid: [
    // Logs then rethrows the original error — failure still surfaces.
    {
      code: "try { f(); } catch (e) { console.error(e); throw e; }",
    },
    // Rethrows without logging.
    {
      code: "try { f(); } catch (e) { throw e; }",
    },
    // Rethrows a wrapped error.
    {
      code: "try { f(); } catch (e) { throw new Error('wrapped', { cause: e }); }",
    },
    // Logs then returns a fallback value — the error is handled.
    {
      code: "function g() { try { return f(); } catch (e) { console.warn(e); return null; } }",
    },
    // Returns a fallback without logging.
    {
      code: "function g() { try { return f(); } catch { return []; } }",
    },
    // Mixed logic: logs but also runs real recovery.
    {
      code: "try { f(); } catch (e) { console.error(e); recover(); }",
    },
    // Calls a real handler (not console).
    {
      code: "try { f(); } catch (e) { reportError(e); }",
    },
    // Console call mixed with a non-console statement assignment.
    {
      code: "let ok = true; try { f(); } catch (e) { console.error(e); ok = false; }",
    },
    // A non-`console` object that happens to have a `.error` method.
    {
      code: "try { f(); } catch (e) { logger.error(e); }",
    },
    // Computed console access is treated conservatively as real work.
    {
      code: "try { f(); } catch (e) { console['error'](e); }",
    },
    // Test file opts out: filename contains `.test.`.
    {
      code: "try { f(); } catch (e) { console.error(e); }",
      filename: "/repo/src/foo.test.ts",
    },
    // Test file opts out: filename contains `.spec.`.
    {
      code: "try { f(); } catch {}",
      filename: "/repo/src/foo.spec.ts",
    },
    // Test file opts out: `__tests__/` path segment.
    {
      code: "try { f(); } catch (e) { console.log(e); }",
      filename: "/repo/src/__tests__/foo.ts",
    },
  ],
  invalid: [
    // Empty catch — silently swallows.
    {
      code: "try { f(); } catch (e) {}",
      errors: [{ messageId: "noLogOnlyCatch" }],
    },
    // Empty catch with no binding.
    {
      code: "try { f(); } catch {}",
      errors: [{ messageId: "noLogOnlyCatch" }],
    },
    // Single console.error then nothing.
    {
      code: "try { f(); } catch (e) { console.error(e); }",
      errors: [{ messageId: "noLogOnlyCatch" }],
    },
    // console.log only.
    {
      code: "try { f(); } catch (e) { console.log('failed', e); }",
      errors: [{ messageId: "noLogOnlyCatch" }],
    },
    // Multiple console calls, all of which just log.
    {
      code: "try { f(); } catch (e) { console.warn('oops'); console.error(e); console.debug('done'); }",
      errors: [{ messageId: "noLogOnlyCatch" }],
    },
    // console.info only.
    {
      code: "try { f(); } catch (e) { console.info(e); }",
      errors: [{ messageId: "noLogOnlyCatch" }],
    },
    // Non-test source file with the same shape still flags.
    {
      code: "try { f(); } catch (e) { console.error(e); }",
      filename: "/repo/src/handler.ts",
      errors: [{ messageId: "noLogOnlyCatch" }],
    },
  ],
});
