/**
 * @fileoverview Disallow `JSON.stringify(err)` on a (heuristically detected)
 * Error value. `JSON.stringify` on an Error produces `"{}"` because the
 * `message` and `stack` properties are non-enumerable, silently throwing away
 * the very information you were trying to log.
 *
 * This is a purely syntactic rule (no type information). It flags
 * `JSON.stringify(x)` only when the first argument is an Identifier whose name
 * either:
 *   1. is the binding of an enclosing `catch (x)` clause in scope, OR
 *   2. matches the conventional error-name pattern /^(e|err|error|ex|exc)$/i.
 *
 * It is deliberately conservative: member expressions (`JSON.stringify(err.message)`),
 * object literals, and arbitrary identifiers (`JSON.stringify(user)`) are not flagged.
 */

import { ESLintUtils, type TSESTree } from "@typescript-eslint/utils";
import type { Scope } from "@typescript-eslint/utils/ts-eslint";

type MessageIds = "noJsonStringifyError";
type Options = readonly [];

const ERROR_NAME_PATTERN = /^(e|err|error|ex|exc)$/i;

/**
 * Walk up the scope chain looking for a `catch` clause whose binding matches
 * `name`. We rely on the scope analysis provided by the parser rather than
 * type information, keeping the rule type-free.
 */
function isCatchBinding(scope: Scope.Scope, name: string): boolean {
  let current: Scope.Scope | null = scope;
  while (current) {
    const variable = current.set.get(name);
    if (variable) {
      for (const def of variable.defs) {
        if (def.type === "CatchClause") {
          return true;
        }
      }
    }
    current = current.upper;
  }
  return false;
}

function isJsonStringify(callee: TSESTree.Expression): boolean {
  return (
    callee.type === "MemberExpression" &&
    !callee.computed &&
    callee.object.type === "Identifier" &&
    callee.object.name === "JSON" &&
    callee.property.type === "Identifier" &&
    callee.property.name === "stringify"
  );
}

export default ESLintUtils.RuleCreator(
  (name) =>
    `https://github.com/sarj-ai/linting/blob/main/packages/typescript/src/rules/${name}.ts`,
)<Options, MessageIds>({
  name: "no-json-stringify-error",
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow `JSON.stringify` on an Error value; it yields `{}` because `message`/`stack` are non-enumerable.",
    },
    schema: [],
    messages: {
      noJsonStringifyError:
        "`JSON.stringify` on an Error yields `{}` because `message`/`stack` are non-enumerable. Log `err.message` / `err.stack`, or use a proper error serializer.",
    },
  },
  defaultOptions: [],
  create(context) {
    return {
      CallExpression(node: TSESTree.CallExpression): void {
        if (!isJsonStringify(node.callee)) {
          return;
        }

        const firstArg = node.arguments[0];
        if (!firstArg || firstArg.type !== "Identifier") {
          return;
        }

        const name = firstArg.name;
        const scope = context.sourceCode.getScope(firstArg);

        if (ERROR_NAME_PATTERN.test(name) || isCatchBinding(scope, name)) {
          context.report({
            node,
            messageId: "noJsonStringifyError",
          });
        }
      },
    };
  },
});
