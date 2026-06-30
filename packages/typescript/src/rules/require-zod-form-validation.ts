import { ESLintUtils, type TSESTree, AST_NODE_TYPES } from "@typescript-eslint/utils";
import type { RuleContext, Scope } from "@typescript-eslint/utils/ts-eslint";

type MessageIds = "missingZodValidation";
type Options = readonly [];

type Ctx = Readonly<RuleContext<MessageIds, Options>>;

// A receiver name that looks like a Zod schema: ends in `Schema`, or uses the
// `Z<Capital>` house convention (e.g. `ZUser`), or the bare `z` builder.
const ZOD_SCHEMA_NAME_RE = /Schema$|^Z[A-Z]/;

/**
 * Walk down a (possibly chained) receiver expression and decide whether it
 * originates from something that looks like a Zod schema — the bare `z` builder
 * (`z.object({...}).parse(...)`), a `Schema`-suffixed identifier
 * (`userSchema.parse(...)`), or a `Z`-prefixed identifier (`ZUser.parse(...)`).
 * Non-Zod receivers like `JSON` / `Date` are intentionally rejected.
 */
const looksLikeZodSchema = (node: TSESTree.Node): boolean => {
  let current: TSESTree.Node = node;
  while (true) {
    if (current.type === AST_NODE_TYPES.Identifier) {
      return current.name === "z" || ZOD_SCHEMA_NAME_RE.test(current.name);
    }
    if (current.type === AST_NODE_TYPES.CallExpression) {
      current = current.callee;
      continue;
    }
    if (current.type === AST_NODE_TYPES.MemberExpression) {
      current = current.object;
      continue;
    }
    return false;
  }
};

/**
 * Matches a Zod validation call: `<ZodSchema>.parse(...)` or
 * `<ZodSchema>.safeParse(...)`. Keys off the *receiver* looking like a Zod
 * schema rather than the method name alone, so `JSON.parse(...)` /
 * `Date.parse(...)` are NOT treated as validation.
 */
const isZodParseCall = (node: TSESTree.Node): boolean => {
  if (node.type !== AST_NODE_TYPES.CallExpression) return false;
  const callee = node.callee;
  if (callee.type !== AST_NODE_TYPES.MemberExpression) return false;
  if (callee.computed) return false;
  if (callee.property.type !== AST_NODE_TYPES.Identifier) return false;
  const method = callee.property.name;
  if (method !== "parse" && method !== "safeParse") return false;
  return looksLikeZodSchema(callee.object);
};

/**
 * Matches an (optionally awaited) `<x>.formData()` call — the canonical way a
 * `FormData` object is obtained from a `Request` / `Response`.
 */
const isFormDataMethodCall = (node: TSESTree.Node): boolean => {
  let current: TSESTree.Node = node;
  if (current.type === AST_NODE_TYPES.AwaitExpression) {
    current = current.argument;
  }
  if (current.type !== AST_NODE_TYPES.CallExpression) return false;
  const callee = current.callee;
  return (
    callee.type === AST_NODE_TYPES.MemberExpression &&
    !callee.computed &&
    callee.property.type === AST_NODE_TYPES.Identifier &&
    callee.property.name === "formData"
  );
};

export default ESLintUtils.RuleCreator(
  (name) =>
    `https://github.com/sarj-ai/linting/blob/main/packages/typescript/src/rules/${name}.ts`,
)<Options, MessageIds>({
  name: "require-zod-form-validation",
  meta: {
    type: "problem",
    docs: {
      description:
        "Require Zod validation (`Schema.parse(...)` / `Schema.safeParse(...)`) when reading values out of a `FormData` object.",
    },
    schema: [],
    messages: {
      missingZodValidation:
        "FormData parsing must use Zod schema validation (e.g., Schema.parse() / Schema.safeParse())",
    },
  },
  defaultOptions: [],
  create(context: Ctx) {
    // A receiver is a FormData source if its name reads like form data, or if
    // it is a binding initialized from a `.formData()` call.
    const isFormSourceIdentifier = (node: TSESTree.Node): boolean => {
      if (node.type !== AST_NODE_TYPES.Identifier) return false;
      if (/formdata/i.test(node.name)) return true;

      let scope: Scope.Scope | null = context.sourceCode.getScope(node);
      while (scope !== null) {
        const variable = scope.set.get(node.name);
        if (variable !== undefined && variable.defs.length === 1) {
          const def = variable.defs[0];
          if (
            def !== undefined &&
            def.type === "Variable" &&
            def.node.type === AST_NODE_TYPES.VariableDeclarator &&
            def.node.init !== null
          ) {
            return isFormDataMethodCall(def.node.init);
          }
          return false;
        }
        scope = scope.upper;
      }
      return false;
    };

    const isFormDataGetCall = (node: TSESTree.CallExpression): boolean => {
      const callee = node.callee;
      if (callee.type !== AST_NODE_TYPES.MemberExpression) return false;
      if (
        callee.property.type !== AST_NODE_TYPES.Identifier ||
        callee.property.name !== "get"
      ) {
        return false;
      }
      return isFormSourceIdentifier(callee.object);
    };

    return {
      CallExpression(node: TSESTree.CallExpression): void {
        if (!isFormDataGetCall(node)) return;

        // Walk up the parent chain to find a surrounding Zod `.parse(...)` /
        // `.safeParse(...)` call. `.parent` is `null` at the Program root, so we
        // must guard for both null and undefined.
        let parent: TSESTree.Node | null | undefined = node.parent;
        while (parent !== null && parent !== undefined) {
          if (isZodParseCall(parent)) return;
          parent = parent.parent;
        }

        context.report({
          node,
          messageId: "missingZodValidation",
        });
      },
    };
  },
});
