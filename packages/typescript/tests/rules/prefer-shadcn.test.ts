import * as tsParser from "@typescript-eslint/parser";
import { RuleTester } from "@typescript-eslint/rule-tester";
import { afterAll, describe, it } from "vitest";

import rule from "../../src/rules/prefer-shadcn.js";

RuleTester.afterAll = afterAll;
RuleTester.describe = describe;
RuleTester.it = it;
RuleTester.itOnly = it.only;

const ruleTester = new RuleTester({
  languageOptions: {
    parser: tsParser,
    parserOptions: {
      ecmaFeatures: { jsx: true },
    },
  },
});

ruleTester.run("prefer-shadcn", rule, {
  valid: [
    // shadcn primitives — the prescribed components.
    { code: "const x = <Input value='' onChange={() => {}} />;" },
    { code: "const x = <Select><option /></Select>;" },
    { code: "const x = <Textarea />;" },
    { code: "const x = <Dialog open />;" },
    // `<button>` and `<table>` were dropped from the forbid list (100% FP).
    { code: "const x = <button type='button'>click</button>;" },
    { code: "const x = <table><tbody /></table>;" },
    // Non-form elements are unrelated.
    { code: "const x = <div className='wrapper' />;" },
  ],
  invalid: [
    {
      code: "const x = <input type='text' />;",
      errors: [{ messageId: "preferShadcn" }],
    },
    {
      code: "const x = <select><option value='a'>a</option></select>;",
      errors: [{ messageId: "preferShadcn" }],
    },
    {
      code: "const x = <textarea rows={4} />;",
      errors: [{ messageId: "preferShadcn" }],
    },
    {
      code: "const x = <dialog open>hi</dialog>;",
      errors: [{ messageId: "preferShadcn" }],
    },
  ],
});
