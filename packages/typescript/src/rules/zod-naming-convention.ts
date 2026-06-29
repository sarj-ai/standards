/**
 * @fileoverview Enforce the `Z`-prefix naming convention for Zod schemas
 * (`ZUser = z.object({...})`).
 *
 * NOTE on audit backing: this is an intentional org-wide convention, not a
 * direct mapping of `readability-and-naming.md` (which governs property-name
 * casing, not schema-variable prefixes). The `Z` prefix lets schemas and their
 * inferred types share a base name (`ZUser` / `type User = z.infer<typeof
 * ZUser>`) without collision. Kept as-is by design.
 */

import { ESLintUtils, type TSESTree, AST_NODE_TYPES } from "@typescript-eslint/utils";

type MessageIds = "zPrefix";
type Options = readonly [];

/**
 * Walks down a (possibly chained) callee like `z.object().extend().refine()` and
 * returns `true` if the chain originates from a bare `z` identifier — i.e. the
 * outermost MemberExpression on the chain has `z` as its receiver.
 */
const calleeChainStartsWithZ = (node: TSESTree.Node): boolean => {
  let current: TSESTree.Node = node;

  while (current.type === AST_NODE_TYPES.MemberExpression) {
    const receiver: TSESTree.Node = current.object;
    if (receiver.type === AST_NODE_TYPES.Identifier && receiver.name === "z") {
      return true;
    }
    if (receiver.type === AST_NODE_TYPES.CallExpression) {
      current = receiver.callee;
      continue;
    }
    return false;
  }

  return false;
};

export default ESLintUtils.RuleCreator(
  (name) =>
    `https://github.com/sarj-ai/linting/blob/main/packages/typescript/src/rules/${name}.ts`,
)<Options, MessageIds>({
  name: "zod-naming-convention",
  meta: {
    type: "suggestion",
    docs: {
      description:
        "Enforce Zod schemas to be named with a Z prefix (e.g. `ZUser = z.object({...})`).",
    },
    schema: [],
    messages: {
      zPrefix: "Zod schema names should start with Z",
    },
  },
  defaultOptions: [],
  create(context) {
    return {
      VariableDeclarator(node: TSESTree.VariableDeclarator): void {
        const init = node.init;
        if (init === null || init === undefined) return;
        if (init.type !== AST_NODE_TYPES.CallExpression) return;

        const callee = init.callee;
        if (callee.type !== AST_NODE_TYPES.MemberExpression) return;

        if (!calleeChainStartsWithZ(callee)) return;

        if (node.id.type !== AST_NODE_TYPES.Identifier) return;
        const variableName = node.id.name;
        if (variableName.startsWith("Z")) return;

        context.report({
          node: node.id,
          messageId: "zPrefix",
        });
      },
    };
  },
});
