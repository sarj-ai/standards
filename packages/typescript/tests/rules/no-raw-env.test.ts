import { RuleTester } from "@typescript-eslint/rule-tester";
import { afterAll, describe, it } from "vitest";

import rule from "../../src/rules/no-raw-env.js";

RuleTester.afterAll = afterAll;
RuleTester.describe = describe;
RuleTester.it = it;
RuleTester.itOnly = it.only;

const ruleTester = new RuleTester();

ruleTester.run("no-raw-env", rule, {
  valid: [
    // Reading from a validated env module is the prescribed pattern.
    { code: "import { env } from '@/env'; const url = env.DATABASE_URL;" },
    // Unrelated member access is fine.
    { code: "const x = process.cwd();" },
    // A property named `env` on something other than `process` is fine.
    { code: "const x = config.env;" },
    // `process["env"]` (computed on `process`) yields the env object as a whole,
    // not a specific unvalidated var — out of scope.
    { code: "const x = process['env'];" },
    // `import.meta.env` on a non-import meta base is unrelated.
    { code: "const x = config.meta.env;" },
  ],
  invalid: [
    {
      code: "const url = process.env.DATABASE_URL;",
      errors: [{ messageId: "noRawEnv" }],
    },
    {
      code: "if (process.env.NODE_ENV === 'production') {}",
      errors: [{ messageId: "noRawEnv" }],
    },
    {
      code: "const { FOO } = process.env;",
      errors: [{ messageId: "noRawEnv" }],
    },
    // Computed access into process.env is just as unvalidated as the dotted form.
    {
      code: "const url = process.env[key];",
      errors: [{ messageId: "noRawEnv" }],
    },
    // Vite's import.meta.env — dotted and computed.
    {
      code: "const dev = import.meta.env.DEV;",
      errors: [{ messageId: "noRawEnv" }],
    },
    {
      code: "const x = import.meta.env.VITE_X;",
      errors: [{ messageId: "noRawEnv" }],
    },
    {
      code: "const x = import.meta.env[key];",
      errors: [{ messageId: "noRawEnv" }],
    },
  ],
});
