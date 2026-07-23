import * as tsParser from "@typescript-eslint/parser";
import { RuleTester } from "@typescript-eslint/rule-tester";
import { afterAll, describe, it } from "vitest";

import rule from "../../src/rules/no-unsafe-cast.js";

RuleTester.afterAll = afterAll;
RuleTester.describe = describe;
RuleTester.it = it;
RuleTester.itOnly = it.only;

const ruleTester = new RuleTester({
  languageOptions: {
    parser: tsParser,
  },
});

ruleTester.run("no-unsafe-cast", rule, {
  valid: [
    { code: "const x = { a: 1 } as const;" },
    { code: "const x = value as SpecificType;" },
    { code: "const x = value satisfies SomeType;" },
    { code: "const x = value as string;" },
    { code: "const x = value as Foo | Bar;" },
    // Single cast through unknown alone is allowed; only the double-cast form is flagged.
    { code: "const x = value as unknown;" },
  ],
  invalid: [
    {
      code: "const x = value as any;",
      errors: [{ messageId: "asAny" }],
    },
    {
      code: "const x = <any>value;",
      errors: [{ messageId: "asAny" }],
    },
    {
      code: "const x = value as unknown as Foo;",
      errors: [{ messageId: "doubleCast" }],
    },
    {
      code: "const x = foo as any as Bar;",
      errors: [{ messageId: "doubleCast" }, { messageId: "asAny" }],
    },
    {
      code: "const x = <Foo>(<unknown>value);",
      errors: [{ messageId: "doubleCast" }],
    },
  ],
});
