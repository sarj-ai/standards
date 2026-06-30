/**
 * @fileoverview Prefer shadcn/ui form primitives over their native HTML
 * counterparts. Limited to form/dialog elements — `<button>` and `<table>`
 * have been removed from the forbid list because they produced 100% false
 * positives during bulbul validation (icon buttons, layout tables).
 */

import { ESLintUtils, type TSESTree } from "@typescript-eslint/utils";

type MessageIds = "preferShadcn";
type Options = readonly [];

const REPLACEMENTS: Readonly<Record<string, string>> = {
  input: "Input",
  select: "Select",
  textarea: "Textarea",
  dialog: "Dialog",
};

export default ESLintUtils.RuleCreator(
  (name) =>
    `https://github.com/sarj-ai/linting/blob/main/packages/typescript/src/rules/${name}.ts`,
)<Options, MessageIds>({
  name: "prefer-shadcn",
  meta: {
    type: "suggestion",
    docs: {
      description:
        "Prefer shadcn/ui form primitives over native `<input>`, `<select>`, `<textarea>`, and `<dialog>` elements.",
    },
    schema: [],
    messages: {
      preferShadcn:
        "Use the shadcn <{{replacement}}> component from @/components/ui/{{lowercase}} instead of native <{{element}}>.",
    },
  },
  defaultOptions: [],
  create(context) {
    return {
      JSXOpeningElement(node: TSESTree.JSXOpeningElement): void {
        // Only lowercase JSXIdentifier names represent native HTML elements.
        // Member expressions (`Foo.Bar`) and namespaces (`svg:path`) are skipped.
        if (node.name.type !== "JSXIdentifier") {
          return;
        }

        const elementName = node.name.name;
        const replacement = REPLACEMENTS[elementName];

        if (replacement === undefined) {
          return;
        }

        context.report({
          node,
          messageId: "preferShadcn",
          data: {
            element: elementName,
            replacement,
            lowercase: elementName,
          },
        });
      },
    };
  },
});
