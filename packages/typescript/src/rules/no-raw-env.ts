/**
 * @fileoverview Disallow direct `process.env` access. Force all env reads
 * through a Zod-validated env module so configuration is typed and validated
 * at startup.
 */

import { ESLintUtils, type TSESTree } from "@typescript-eslint/utils";

type MessageIds = "noRawEnv";
type Options = readonly [];

/** True for the `process.env` member node (dotted or as the base of `process.env[key]`). */
function isProcessEnv(node: TSESTree.MemberExpression): boolean {
  return (
    !node.computed &&
    node.object.type === "Identifier" &&
    node.object.name === "process" &&
    node.property.type === "Identifier" &&
    node.property.name === "env"
  );
}

/** True for the `import.meta.env` member node (dotted or as the base of `import.meta.env[key]`). */
function isImportMetaEnv(node: TSESTree.MemberExpression): boolean {
  return (
    !node.computed &&
    node.property.type === "Identifier" &&
    node.property.name === "env" &&
    node.object.type === "MetaProperty" &&
    node.object.meta.name === "import" &&
    node.object.property.name === "meta"
  );
}

// Build-time constants that bundlers (webpack/Vite) statically replace — there is
// no runtime env value to route through the validated layer, so they are exempt.
const BUILD_TIME_CONSTANTS: ReadonlySet<string> = new Set([
  "NODE_ENV",
  "MODE",
  "DEV",
  "PROD",
  "SSR",
]);

/** True when `node` is the base of a build-time-constant access like `process.env.NODE_ENV`. */
function isBuildTimeConstantAccess(node: TSESTree.MemberExpression): boolean {
  const parent = node.parent;
  return (
    parent.type === "MemberExpression" &&
    parent.object === node &&
    !parent.computed &&
    parent.property.type === "Identifier" &&
    BUILD_TIME_CONSTANTS.has(parent.property.name)
  );
}

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
        if (
          (isProcessEnv(node) || isImportMetaEnv(node)) &&
          !isBuildTimeConstantAccess(node)
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
