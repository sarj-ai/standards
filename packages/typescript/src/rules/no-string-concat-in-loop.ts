/**
 * @fileoverview Disallow string accumulation via `+=` inside a loop, which is
 * the classic O(n^2) string-building antipattern: each `+=` rebuilds the whole
 * string. Push the parts onto an array and `arr.join("")` after the loop
 * instead.
 *
 * This is a purely SYNTACTIC rule — it uses scope analysis (not the type
 * service) to confirm the left-hand side was declared with a string-literal
 * initializer (`let s = ""`, `= "..."`, or a template literal). It is
 * deliberately conservative: when the initializer type cannot be determined
 * (no initializer, a non-literal expression, a parameter, etc.) the `+=` is
 * NOT flagged. This mirrors the Python rule SARJ002.
 */

import { ESLintUtils, type TSESTree } from "@typescript-eslint/utils";
import type { Scope } from "@typescript-eslint/utils/ts-eslint";

type MessageIds = "noStringConcatInLoop";
type Options = readonly [];

const LOOP_NODE_TYPES = new Set<string>([
  "ForStatement",
  "ForOfStatement",
  "ForInStatement",
  "WhileStatement",
  "DoWhileStatement",
]);

/**
 * Returns true if the given expression node is a string-producing literal:
 * a string `Literal` (`""`, `"..."`, `'...'`) or a `TemplateLiteral`.
 */
function isStringLiteralInit(node: TSESTree.Expression | null): boolean {
  if (node === null) {
    return false;
  }
  if (node.type === "TemplateLiteral") {
    return true;
  }
  if (node.type === "Literal") {
    return typeof node.value === "string";
  }
  return false;
}

/**
 * Walk the chain of enclosing scopes to find the variable definition for the
 * given identifier name. Returns the resolved `Variable`, or `undefined` if it
 * cannot be found (e.g. an undeclared global or an out-of-scope reference).
 */
function findVariable(
  scope: Scope.Scope,
  name: string,
): Scope.Variable | undefined {
  let current: Scope.Scope | null = scope;
  while (current !== null) {
    const variable = current.variables.find((v) => v.name === name);
    if (variable !== undefined) {
      return variable;
    }
    current = current.upper;
  }
  return undefined;
}

/**
 * Returns true if the variable was declared with a string-literal initializer.
 * Conservative: if the variable has no single string-initialized declarator
 * (no init, non-literal init, multiple conflicting declarators), returns false.
 */
function isStringInitializedVariable(variable: Scope.Variable): boolean {
  // A variable can technically have multiple declarators (e.g. via `var`
  // hoisting / redeclaration). Only treat it as string-initialized when there
  // is exactly one declarator and it has a string-literal initializer.
  if (variable.defs.length !== 1) {
    return false;
  }
  const def = variable.defs[0];
  if (def === undefined || def.type !== "Variable") {
    // Parameters, function names, imports, etc. — type unknown, don't flag.
    return false;
  }
  const declarator = def.node;
  if (declarator.type !== "VariableDeclarator") {
    return false;
  }
  return isStringLiteralInit(declarator.init);
}

/**
 * Returns true if `node` is contained within the body of a loop statement.
 * Walks ancestors and, for each loop, ensures the node is inside the loop's
 * BODY (not its test/init/update clauses, which run a bounded number of times
 * relative to the body and aren't the antipattern we target).
 */
function isInsideLoopBody(node: TSESTree.Node): boolean {
  let child: TSESTree.Node = node;
  let parent = node.parent;
  while (parent !== undefined && parent !== null) {
    if (LOOP_NODE_TYPES.has(parent.type)) {
      // `body` is the property that holds the looped statements for every
      // loop variant we care about.
      const loop = parent as
        | TSESTree.ForStatement
        | TSESTree.ForOfStatement
        | TSESTree.ForInStatement
        | TSESTree.WhileStatement
        | TSESTree.DoWhileStatement;
      if (loop.body === child) {
        return true;
      }
    }
    child = parent;
    parent = parent.parent;
  }
  return false;
}

export default ESLintUtils.RuleCreator(
  (name) =>
    `https://github.com/sarj-ai/linting/blob/main/packages/typescript/src/rules/${name}.ts`,
)<Options, MessageIds>({
  name: "no-string-concat-in-loop",
  meta: {
    type: "suggestion",
    docs: {
      description:
        "Disallow O(n^2) string building via `+=` on a string variable inside a loop; push parts to an array and `join` instead.",
    },
    schema: [],
    messages: {
      noStringConcatInLoop:
        "Avoid building a string with `+=` inside a loop — this is O(n^2). Push the parts onto an array and use `arr.join(\"\")` after the loop.",
    },
  },
  defaultOptions: [],
  create(context) {
    return {
      AssignmentExpression(node: TSESTree.AssignmentExpression): void {
        // Only the compound `+=` operator builds up a value.
        if (node.operator !== "+=") {
          return;
        }
        // The LHS must be a plain variable reference.
        if (node.left.type !== "Identifier") {
          return;
        }
        // Must occur inside a loop body, else it's a one-shot append.
        if (!isInsideLoopBody(node)) {
          return;
        }

        const scope = context.sourceCode.getScope(node);
        const variable = findVariable(scope, node.left.name);
        // Conservative: can't resolve the declaration -> don't flag.
        if (variable === undefined) {
          return;
        }
        // Only flag when we can confirm the LHS was string-initialized; a
        // numeric initializer (or anything non-string) is intentionally
        // excluded to avoid false positives.
        if (!isStringInitializedVariable(variable)) {
          return;
        }

        context.report({
          node,
          messageId: "noStringConcatInLoop",
        });
      },
    };
  },
});
