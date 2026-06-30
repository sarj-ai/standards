import { ESLintUtils, type TSESTree, AST_NODE_TYPES } from "@typescript-eslint/utils";

type MessageIds = "missingAssertNever";
type Options = readonly [];

/**
 * Matches a call to `assertNever(...)` — either the bare identifier form
 * (`assertNever(x)`) or a namespaced member form (`utils.assertNever(x)`).
 */
const isAssertNeverCall = (expression: TSESTree.Expression): boolean => {
  if (expression.type !== AST_NODE_TYPES.CallExpression) return false;
  const callee = expression.callee;
  if (callee.type === AST_NODE_TYPES.Identifier) {
    return callee.name === "assertNever";
  }
  if (
    callee.type === AST_NODE_TYPES.MemberExpression &&
    !callee.computed &&
    callee.property.type === AST_NODE_TYPES.Identifier
  ) {
    return callee.property.name === "assertNever";
  }
  return false;
};

const statementContainsAssertNever = (
  statement: TSESTree.Statement,
): boolean => {
  if (statement.type === AST_NODE_TYPES.ExpressionStatement) {
    return isAssertNeverCall(statement.expression);
  }
  if (statement.type === AST_NODE_TYPES.ThrowStatement) {
    return isAssertNeverCall(statement.argument);
  }
  if (statement.type === AST_NODE_TYPES.ReturnStatement) {
    return (
      statement.argument !== null && isAssertNeverCall(statement.argument)
    );
  }
  // Recurse into block-scoped default bodies like `default: { ... }`
  if (statement.type === AST_NODE_TYPES.BlockStatement) {
    return statement.body.some(statementContainsAssertNever);
  }
  return false;
};

/**
 * Returns true if the statement performs some runtime work. An empty statement
 * or an empty block does nothing; everything else (`return`, `throw`, `break`,
 * a function call, an `if`, ...) is treated as legitimate runtime handling of
 * the default case.
 */
const isRuntimeHandlingStatement = (statement: TSESTree.Statement): boolean => {
  if (statement.type === AST_NODE_TYPES.EmptyStatement) return false;
  if (statement.type === AST_NODE_TYPES.BlockStatement) {
    return statement.body.some(isRuntimeHandlingStatement);
  }
  return true;
};

export default ESLintUtils.RuleCreator(
  (name) =>
    `https://github.com/sarj-ai/linting/blob/main/packages/typescript/src/rules/${name}.ts`,
)<Options, MessageIds>({
  name: "require-assert-never",
  meta: {
    type: "problem",
    docs: {
      description:
        "Require an exhaustive-style switch whose `default` case does no runtime work to call `assertNever(_)` so that discriminated unions are exhaustively checked at compile time. Switches with a legitimate runtime default (a reducer's `return state`, an HTTP-status `return fallback()`, a `break`, a `throw`, etc.) are left alone.",
    },
    schema: [],
    messages: {
      missingAssertNever:
        "Empty switch `default` case — add runtime handling or call `assertNever()` so the discriminated union is exhaustively checked at compile time.",
    },
  },
  defaultOptions: [],
  create(context) {
    return {
      SwitchStatement(node: TSESTree.SwitchStatement): void {
        const defaultCase = node.cases.find(
          (caseNode): caseNode is TSESTree.SwitchCase => caseNode.test === null,
        );
        // No `default` at all is fine — we don't demand exhaustiveness of every
        // switch, only of those that opted into a (no-op) default.
        if (!defaultCase) return;

        // An explicit `assertNever(...)` is the canonical exhaustiveness check.
        if (defaultCase.consequent.some(statementContainsAssertNever)) return;

        // A default that does real runtime work (return a fallback, break,
        // throw, log, ...) is legitimate — don't demand assertNever there.
        if (defaultCase.consequent.some(isRuntimeHandlingStatement)) return;

        // Otherwise the default is empty / a pure no-op: flag it.
        context.report({
          node: defaultCase,
          messageId: "missingAssertNever",
        });
      },
    };
  },
});
