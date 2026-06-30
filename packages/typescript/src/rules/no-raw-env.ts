/**
 * @fileoverview Disallow direct `process.env` access. Force all env reads
 * through a Zod-validated env module so configuration is typed and validated
 * at startup.
 */

import { ESLintUtils, type TSESTree } from "@typescript-eslint/utils";

type MessageIds = "noRawEnv";
type Options = readonly [];

export default ESLintUtils.RuleCreator(
  (name) =>
    `https://github.com/sarj-ai/linting/blob/main/packages/typescript/src/rules/${name}.ts`,
)<Options, MessageIds>({
  name: "no-raw-env",
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow direct `process.env` access; use a Zod-validated env module instead.",
    },
    schema: [],
    messages: {
      noRawEnv:
        "Do not read from `process.env` directly. Import the Zod-validated env module instead so values are typed and validated at startup.",
    },
  },
  defaultOptions: [],
  create(context) {
    return {
      MemberExpression(node: TSESTree.MemberExpression): void {
        if (node.computed) {
          // Skip dynamic accesses like process["env"] — extremely rare and out of scope.
          return;
        }
        if (
          node.object.type === "Identifier" &&
          node.object.name === "process" &&
          node.property.type === "Identifier" &&
          node.property.name === "env"
        ) {
          context.report({
            node,
            messageId: "noRawEnv",
          });
        }
      },
    };
  },
});
