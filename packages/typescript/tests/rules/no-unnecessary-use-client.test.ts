import { RuleTester } from "@typescript-eslint/rule-tester";
import { afterAll, describe, it } from "vitest";

import rule from "../../src/rules/no-unnecessary-use-client.js";

RuleTester.afterAll = afterAll;
RuleTester.describe = describe;
RuleTester.it = it;
RuleTester.itOnly = it.only;

const ruleTester = new RuleTester({
  languageOptions: {
    parserOptions: {
      ecmaFeatures: { jsx: true },
    },
  },
});

ruleTester.run("no-unnecessary-use-client", rule, {
  valid: [
    // No directive.
    { code: "export default function X() { return <div />; }" },
    // Directive + hook.
    {
      code: "'use client'; import { useState } from 'react'; export default function X() { const [n] = useState(0); return <div>{n}</div>; }",
    },
    // Directive + event handler.
    {
      code: "'use client'; export default function X() { return <button onClick={() => {}}>x</button>; }",
    },
    // Directive + React.useState (namespaced hook).
    {
      code: "'use client'; export default function X() { const [n] = React.useState(0); return <div>{n}</div>; }",
    },
    // Directive + browser global.
    {
      code: "'use client'; export default function X() { return <div>{typeof window}</div>; }",
    },
    // Directive + client-only import.
    {
      code: "'use client'; import * as Dialog from '@radix-ui/react-dialog'; export default function X() { return <Dialog.Root />; }",
    },
    // Directive + class declaration (client-side only).
    {
      code: "'use client'; class Thing {} export default function X() { return <div />; }",
    },
  ],
  invalid: [
    {
      code: "'use client'; export default function X() { return <div>hello</div>; }",
      errors: [{ messageId: "unnecessaryUseClient" }],
    },
    {
      code: "'use client'; export default function X({ name }) { return <div>{name}</div>; }",
      errors: [{ messageId: "unnecessaryUseClient" }],
    },
  ],
});
