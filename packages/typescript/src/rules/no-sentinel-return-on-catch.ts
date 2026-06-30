/**
 * @fileoverview Disallow silently swallowing an error in a `catch` clause by
 * returning a "sentinel" empty value as the final/only statement.
 *
 * A `catch` block whose last statement is `return null` / `return undefined` /
 * `return false` / `return []` / `return {}` (and which never `throw`s) discards
 * the caught error entirely. Downstream callers can't distinguish a genuine
 * empty result from a failure, which is a frequent source of silent data loss
 * and broken idempotency decisions.
 *
 * This rule is deliberately conservative — it prefers false negatives over
 * false positives. It does NOT flag:
 *   - catch blocks that `throw`/rethrow anywhere in their body,
 *   - returns of a computed/meaningful value (calls, identifiers, member
 *     expressions, non-empty literals),
 *   - `return 0` / `return ""`, which are often legitimate results.
 */

import {
  ESLintUtils,
  type TSESTree,
  AST_NODE_TYPES,
} from "@typescript-eslint/utils";

type MessageIds = "noSentinelReturn";
type Options = readonly [];

/** Whether a returned expression is one of the swallowing sentinels. */
function isSentinelArgument(arg: TSESTree.Expression | null): boolean {
  if (arg === null) {
    // `return;` — bare return is not in scope (no value-shaped sentinel).
    return false;
  }

  // `return null`
  if (arg.type === AST_NODE_TYPES.Literal && arg.value === null) {
    return true;
  }

  // `return false`
  if (arg.type === AST_NODE_TYPES.Literal && arg.value === false) {
    return true;
  }

  // `return undefined`
  if (arg.type === AST_NODE_TYPES.Identifier && arg.name === "undefined") {
    return true;
  }

  // `return []` — empty array literal only.
  if (arg.type === AST_NODE_TYPES.ArrayExpression && arg.elements.length === 0) {
    return true;
  }

  // `return {}` — empty object literal only.
  if (
    arg.type === AST_NODE_TYPES.ObjectExpression &&
    arg.properties.length === 0
  ) {
    return true;
  }

  return false;
}

/**
 * Does this subtree contain a `throw` statement, ignoring nested functions
 * (a throw inside a nested function/arrow doesn't rethrow for *this* catch)?
 */
function containsThrow(node: TSESTree.Node): boolean {
  let found = false;

  const visit = (current: TSESTree.Node): void => {
    if (found) {
      return;
    }

    if (current.type === AST_NODE_TYPES.ThrowStatement) {
      found = true;
      return;
    }

    // Do not descend into nested function scopes — a throw there does not
    // propagate out of the current catch synchronously.
    if (
      current.type === AST_NODE_TYPES.FunctionDeclaration ||
      current.type === AST_NODE_TYPES.FunctionExpression ||
      current.type === AST_NODE_TYPES.ArrowFunctionExpression
    ) {
      return;
    }

    for (const key of Object.keys(current)) {
      if (key === "parent") {
        continue;
      }
      const value = (current as unknown as Record<string, unknown>)[key];
      if (Array.isArray(value)) {
        for (const child of value) {
          if (isNode(child)) {
            visit(child);
          }
        }
      } else if (isNode(value)) {
        visit(value);
      }
    }
  };

  visit(node);
  return found;
}

function isNode(value: unknown): value is TSESTree.Node {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as { type?: unknown }).type === "string"
  );
}

export default ESLintUtils.RuleCreator(
  (name) =>
    `https://github.com/sarj-ai/linting/blob/main/packages/typescript/src/rules/${name}.ts`,
)<Options, MessageIds>({
  name: "no-sentinel-return-on-catch",
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow swallowing a caught error by returning an empty sentinel (`null`, `undefined`, `false`, `[]`, `{}`) as the final statement of a `catch` block.",
    },
    schema: [],
    messages: {
      noSentinelReturn:
        "This `catch` block swallows the error by returning an empty sentinel. Rethrow it, return a typed Result, or handle the error explicitly.",
    },
  },
  defaultOptions: [],
  create(context) {
    return {
      CatchClause(node: TSESTree.CatchClause): void {
        const body = node.body.body;
        if (body.length === 0) {
          return;
        }

        const last = body[body.length - 1];
        if (last === undefined || last.type !== AST_NODE_TYPES.ReturnStatement) {
          return;
        }

        if (!isSentinelArgument(last.argument)) {
          return;
        }

        // Conservative: if the catch body throws/rethrows anywhere, it's not
        // silently swallowing the error.
        if (containsThrow(node.body)) {
          return;
        }

        context.report({
          node: last,
          messageId: "noSentinelReturn",
        });
      },
    };
  },
});
