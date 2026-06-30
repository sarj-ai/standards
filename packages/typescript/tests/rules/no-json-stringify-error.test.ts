import * as tsParser from "@typescript-eslint/parser";
import { RuleTester } from "@typescript-eslint/rule-tester";
import { afterAll, describe, it } from "vitest";

import rule from "../../src/rules/no-json-stringify-error.js";

RuleTester.afterAll = afterAll;
RuleTester.describe = describe;
RuleTester.it = it;
RuleTester.itOnly = it.only;

const ruleTester = new RuleTester({
  languageOptions: {
    parser: tsParser,
  },
});

ruleTester.run("no-json-stringify-error", rule, {
  valid: [
    // Stringifying a non-error object is fine.
    { code: "JSON.stringify(user);" },
    // Object literal is fine.
    { code: "JSON.stringify({ a: 1 });" },
    // Arbitrary identifier that isn't an error name and isn't a catch binding.
    { code: "const payload = {}; JSON.stringify(payload);" },
    // Accessing a property of the error is the recommended escape hatch.
    { code: "try { f(); } catch (err) { JSON.stringify(err.message); }" },
    { code: "try { f(); } catch (err) { JSON.stringify(err.stack); }" },
    // A function whose param is named `data` (not an error name).
    { code: "function f(data) { return JSON.stringify(data); }" },
    // Names that merely contain an error-like substring don't match the anchored regex.
    { code: "JSON.stringify(errors);" },
    { code: "JSON.stringify(emailAddress);" },
    { code: "JSON.stringify(exception);" },
    // Not JSON.stringify at all.
    { code: "const err = {}; serialize(err);" },
    // Different object than JSON.
    { code: "const err = {}; MyJSON.stringify(err);" },
    // No arguments.
    { code: "JSON.stringify();" },
  ],
  invalid: [
    // A `catch` binding passed directly, even with an unconventional name.
    {
      code: "try { f(); } catch (problem) { JSON.stringify(problem); }",
      errors: [{ messageId: "noJsonStringifyError" }],
    },
    // Conventional error names by pattern.
    {
      code: "JSON.stringify(err);",
      errors: [{ messageId: "noJsonStringifyError" }],
    },
    {
      code: "JSON.stringify(error);",
      errors: [{ messageId: "noJsonStringifyError" }],
    },
    {
      code: "JSON.stringify(e);",
      errors: [{ messageId: "noJsonStringifyError" }],
    },
    {
      code: "JSON.stringify(ex);",
      errors: [{ messageId: "noJsonStringifyError" }],
    },
    {
      code: "JSON.stringify(exc);",
      errors: [{ messageId: "noJsonStringifyError" }],
    },
    // Case-insensitive name match.
    {
      code: "JSON.stringify(Error);",
      errors: [{ messageId: "noJsonStringifyError" }],
    },
    // catch binding inside a nested scope, conventional name.
    {
      code: "try { f(); } catch (err) { const wrap = () => JSON.stringify(err); }",
      errors: [{ messageId: "noJsonStringifyError" }],
    },
    // catch binding with unconventional name, used in nested scope.
    {
      code: "try { f(); } catch (boom) { const wrap = () => JSON.stringify(boom); }",
      errors: [{ messageId: "noJsonStringifyError" }],
    },
  ],
});
