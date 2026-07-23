/**
 * @fileoverview Disallow `JSON.stringify(err)` on a (heuristically detected)
 * Error value. `JSON.stringify` on an Error produces `"{}"` because the
 * `message` and `stack` properties are non-enumerable, silently throwing away
 * the very information you were trying to log.
 *
 * This is a purely syntactic rule (no type information). It flags
 * `JSON.stringify(x)` when the first argument is either:
 *   1. an Identifier that is the binding of an enclosing `catch (x)` clause, or
 *      matches the conventional error-name pattern /^(e|err|error|ex|exc)$/i, OR
 *   2. a member expression denoting an error value (`err.cause`, `this.lastError`) —
 *      an error-suggesting property name, or an error-named base whose property is
 *      not a plain string accessor (`.message` / `.stack` / `.name`).
 *
 * It suppresses the report inside the non-error branch of an `x instanceof Error`
 * guard (`x instanceof Error ? x : JSON.stringify(x)`), where stringifying the
 * non-Error fallback is exactly correct.
 *
 * Object literals and arbitrary identifiers (`JSON.stringify(user)`) are not flagged.
 */

import { ESLintUtils, type TSESTree } from "@typescript-eslint/utils";
import type { Scope, SourceCode } from "@typescript-eslint/utils/ts-eslint";

type MessageIds = "noJsonStringifyError";
type Options = readonly [];

const ERROR_NAME_PATTERN = /^(e|err|error|ex|exc)$/i;

/** Property names whose value is itself an error object (unsafe to stringify). */
const ERROR_PROP_PATTERN = /^(cause|lastError|error|err|exception|originalError|innerError)$/i;

/** Property names whose value is a plain string — the recommended escape hatch. */
const SAFE_STRING_PROPS: ReadonlySet<string> = new Set(["message", "stack", "name"]);

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

/**
 * True if a member-expression argument (`err.cause`, `this.lastError`) denotes an
 * Error value: an error-suggesting property name, or an error-suggesting base whose
 * property is not a known string accessor (`.message` / `.stack` / `.name`).
 */
function memberSuggestsError(
  member: TSESTree.MemberExpression,
  scope: Scope.Scope,
): boolean {
  const propName =
    !member.computed && member.property.type === "Identifier" ? member.property.name : null;

  if (propName !== null && ERROR_PROP_PATTERN.test(propName)) {
    return true;
  }

  const base = member.object;
  const baseSuggestsError =
    base.type === "Identifier" &&
    (ERROR_NAME_PATTERN.test(base.name) || isCatchBinding(scope, base.name));
  if (baseSuggestsError) {
    return propName === null || !SAFE_STRING_PROPS.has(propName.toLowerCase());
  }

  return false;
}

/** The subject `x` of an `x instanceof Error` test, or null. */
function instanceofErrorSubject(
  test: TSESTree.Expression,
): TSESTree.Expression | null {
  if (
    test.type === "BinaryExpression" &&
    test.operator === "instanceof" &&
    test.right.type === "Identifier" &&
    test.right.name === "Error"
  ) {
    return test.left;
  }
  return null;
}

/** Names of a user-defined type-guard predicate: `isErrorLike`, `isError`, `hasErrorShape`. */
const TYPE_GUARD_PATTERN = /^(is|has)[A-Z]/;

/** The narrowed subject `x` of a user-defined type-guard call `isFoo(x)`, or null. */
function typeGuardSubject(
  test: TSESTree.Expression,
): TSESTree.Expression | null {
  const arg = test.type === "CallExpression" ? test.arguments[0] : undefined;
  if (
    test.type === "CallExpression" &&
    test.callee.type === "Identifier" &&
    TYPE_GUARD_PATTERN.test(test.callee.name) &&
    test.arguments.length === 1 &&
    arg !== undefined &&
    arg.type !== "SpreadElement"
  ) {
    return arg;
  }
  return null;
}

/**
 * The subject `x` of a positive error-narrowing test — `x instanceof Error` or a
 * user-defined guard `isErrorLike(x)`. In both, the value IS the error in the
 * truthy branch, so `JSON.stringify(x)` belongs in the falsy (alternate) branch.
 */
function positiveErrorSubject(
  test: TSESTree.Expression,
): TSESTree.Expression | null {
  return instanceofErrorSubject(test) ?? typeGuardSubject(test);
}

/** The subject `x` of a negated error-narrowing test — `!(x instanceof Error)` / `!isErrorLike(x)`. */
function negatedInstanceofErrorSubject(
  test: TSESTree.Expression,
): TSESTree.Expression | null {
  if (test.type === "UnaryExpression" && test.operator === "!") {
    return positiveErrorSubject(test.argument);
  }
  return null;
}

/** Whether a branch statement unconditionally exits (its last statement returns/throws). */
function branchTerminates(branch: TSESTree.Statement): boolean {
  const body = branch.type === "BlockStatement" ? branch.body : [branch];
  const last = body[body.length - 1];
  return (
    last !== undefined &&
    (last.type === "ReturnStatement" || last.type === "ThrowStatement")
  );
}

/**
 * True if an earlier guard `if (isErrorLike(arg)) return …` (or `instanceof Error`)
 * in an enclosing block narrows `argExpr` away from the error case before `node`,
 * so by the time `JSON.stringify(arg)` runs the value is the non-Error fallback.
 */
function isNarrowedByEarlyReturn(
  node: TSESTree.Node,
  argExpr: TSESTree.Expression,
  sourceCode: Readonly<SourceCode>,
): boolean {
  const argText = sourceCode.getText(argExpr);
  let current: TSESTree.Node | undefined = node.parent;
  while (current) {
    if (current.type === "BlockStatement" || current.type === "Program") {
      for (const stmt of current.body) {
        if (stmt.range[0] >= node.range[0]) {
          break;
        }
        if (
          stmt.type === "IfStatement" &&
          stmt.alternate === null &&
          branchTerminates(stmt.consequent)
        ) {
          const subject = positiveErrorSubject(stmt.test);
          if (subject && sourceCode.getText(subject) === argText) {
            return true;
          }
        }
      }
    }
    current = current.parent;
  }
  return false;
}

function nodeWithin(node: TSESTree.Node, container: TSESTree.Node | null): boolean {
  return (
    container !== null &&
    node.range[0] >= container.range[0] &&
    node.range[1] <= container.range[1]
  );
}

/**
 * True if `node` sits in the NON-error branch of an `argExpr instanceof Error`
 * guard — the branch where `argExpr` is provably not an Error, so stringifying it
 * is the correct fallback. Handles both the ternary and `if`/`else` shapes,
 * including the negated `!(x instanceof Error)` form.
 */
function isGuardedByInstanceofError(
  node: TSESTree.Node,
  argExpr: TSESTree.Expression,
  sourceCode: Readonly<SourceCode>,
): boolean {
  const argText = sourceCode.getText(argExpr);
  const sameSubject = (subject: TSESTree.Expression): boolean =>
    sourceCode.getText(subject) === argText;

  let current: TSESTree.Node | undefined = node.parent;
  while (current) {
    if (current.type === "ConditionalExpression") {
      const subject = positiveErrorSubject(current.test);
      if (subject && sameSubject(subject) && nodeWithin(node, current.alternate)) {
        return true;
      }
      const negated = negatedInstanceofErrorSubject(current.test);
      if (negated && sameSubject(negated) && nodeWithin(node, current.consequent)) {
        return true;
      }
    } else if (current.type === "IfStatement") {
      const subject = positiveErrorSubject(current.test);
      if (subject && sameSubject(subject) && nodeWithin(node, current.alternate)) {
        return true;
      }
      const negated = negatedInstanceofErrorSubject(current.test);
      if (negated && sameSubject(negated) && nodeWithin(node, current.consequent)) {
        return true;
      }
    }
    current = current.parent;
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
        if (!firstArg) {
          return;
        }

        const scope = context.sourceCode.getScope(firstArg);

        let suggestsError: boolean;
        if (firstArg.type === "Identifier") {
          suggestsError =
            ERROR_NAME_PATTERN.test(firstArg.name) || isCatchBinding(scope, firstArg.name);
        } else if (firstArg.type === "MemberExpression") {
          suggestsError = memberSuggestsError(firstArg, scope);
        } else {
          return;
        }

        if (!suggestsError) {
          return;
        }

        if (
          isGuardedByInstanceofError(node, firstArg, context.sourceCode) ||
          isNarrowedByEarlyReturn(node, firstArg, context.sourceCode)
        ) {
          return;
        }

        context.report({
          node,
          messageId: "noJsonStringifyError",
        });
      },
    };
  },
});
