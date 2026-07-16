/**
 * @fileoverview Require that a new error thrown inside a `catch (err)` clause
 * references the caught error — most idiomatically as
 * `new Error(message, { cause: err })`. Throwing a fresh error that never
 * mentions the original discards its stack trace and context, which makes the
 * eventual log/report point at the wrapper instead of the root cause.
 *
 * This is the TypeScript counterpart of Python's B904
 * (`raise ... from err` inside `except`), which is already enforced org-wide.
 *
 * What is flagged: a `throw new <X>(...)` where `<X>` is `Error` or any
 * constructor whose (final) name ends with `Error` (`TypeError`, `SarjError`,
 * `errors.HttpError`, ...), lexically inside a `catch` with an identifier
 * binding, when that identifier appears NOWHERE in the constructor arguments
 * — not in the message expression, not in an options object (`{ cause: err }`),
 * not positionally.
 *
 * NOT flagged: rethrowing the caught error (`throw err`), any argument that
 * references the caught identifier (`new Error(err.message)`,
 * `` new Error(`x: ${err}`) ``, `new HttpError(500, err)`), and constructors
 * whose name does not end with `Error`.
 *
 * KNOWN GAPS (false negatives) — the rule is deliberately conservative:
 *   - Throws inside a nested function/arrow defined in the catch body are
 *     skipped (they don't propagate synchronously, and the enclosing-catch
 *     walk stops at function boundaries).
 *   - Destructured (`catch ({ message })`) and omitted (`catch {}`) bindings
 *     are skipped — there is no identifier to require.
 *   - Any appearance of the caught identifier in the arguments counts, even a
 *     shadowed one (e.g. inside an inline arrow with a same-named parameter)
 *     — this is a purely syntactic check, not a scope analysis.
 *   - Error-like classes whose name does not end with `Error` (`Failure`,
 *     `Panic`) are not recognized.
 */

import {
  ESLintUtils,
  type TSESTree,
  AST_NODE_TYPES,
} from "@typescript-eslint/utils";

type MessageIds = "missingCause";
type Options = readonly [];

const ERROR_NAME_PATTERN = /Error$/;

/**
 * Returns the constructor's simple name: `Error` for `new Error(...)`,
 * `HttpError` for `new errors.HttpError(...)`. Undefined for anything else.
 */
function errorConstructorName(
  callee: TSESTree.Expression,
): string | undefined {
  if (callee.type === AST_NODE_TYPES.Identifier) {
    return callee.name;
  }
  if (
    callee.type === AST_NODE_TYPES.MemberExpression &&
    !callee.computed &&
    callee.property.type === AST_NODE_TYPES.Identifier
  ) {
    return callee.property.name;
  }
  return undefined;
}

/**
 * Walks up from a `throw` to the nearest enclosing `catch` clause, without
 * crossing function boundaries (a throw inside a nested function does not
 * propagate synchronously out of this catch). Returns the catch's identifier
 * binding, or undefined when there is none to require.
 */
function findEnclosingCatchParam(
  node: TSESTree.ThrowStatement,
): TSESTree.Identifier | undefined {
  let current: TSESTree.Node | undefined = node.parent;

  while (current) {
    if (
      current.type === AST_NODE_TYPES.FunctionDeclaration ||
      current.type === AST_NODE_TYPES.FunctionExpression ||
      current.type === AST_NODE_TYPES.ArrowFunctionExpression
    ) {
      return undefined;
    }

    if (current.type === AST_NODE_TYPES.CatchClause) {
      const param = current.param;
      if (param !== null && param.type === AST_NODE_TYPES.Identifier) {
        return param;
      }
      // `catch {}` / destructured binding — nothing to require.
      return undefined;
    }

    current = current.parent;
  }

  return undefined;
}

function isNode(value: unknown): value is TSESTree.Node {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as { type?: unknown }).type === "string"
  );
}

/**
 * True when the subtree contains an Identifier REFERENCE with the given name.
 * Non-computed member-access property names (`other.err`) and non-computed
 * object-literal keys (`{ err: other }`) are name positions, not references,
 * and are excluded.
 */
function referencesName(node: TSESTree.Node, name: string): boolean {
  if (node.type === AST_NODE_TYPES.Identifier) {
    return node.name === name;
  }

  if (node.type === AST_NODE_TYPES.MemberExpression) {
    if (referencesName(node.object, name)) {
      return true;
    }
    return node.computed ? referencesName(node.property, name) : false;
  }

  if (node.type === AST_NODE_TYPES.Property) {
    if (node.computed && referencesName(node.key, name)) {
      return true;
    }
    // Shorthand `{ err }` is covered: its value IS the identifier.
    return referencesName(node.value, name);
  }

  for (const key of Object.keys(node)) {
    if (key === "parent") {
      continue;
    }
    const value = (node as unknown as Record<string, unknown>)[key];
    if (Array.isArray(value)) {
      for (const child of value) {
        if (isNode(child) && referencesName(child, name)) {
          return true;
        }
      }
    } else if (isNode(value) && referencesName(value, name)) {
      return true;
    }
  }

  return false;
}

export default ESLintUtils.RuleCreator(
  (name) =>
    `https://github.com/sarj-ai/linting/blob/main/packages/typescript/src/rules/${name}.ts`,
)<Options, MessageIds>({
  name: "require-error-cause",
  meta: {
    type: "problem",
    docs: {
      description:
        "Require new errors thrown inside a `catch (err)` clause to reference the caught error (e.g. `new Error(message, { cause: err })`), preserving the original stack and context.",
    },
    schema: [],
    messages: {
      missingCause:
        "This `throw` inside `catch ({{caught}})` creates a new error that never references `{{caught}}`, discarding the original stack trace and context. Pass it along, e.g. `new Error(message, { cause: {{caught}} })`. (Parity with Python's B904, enforced org-wide.)",
    },
  },
  defaultOptions: [],
  create(context) {
    return {
      ThrowStatement(node: TSESTree.ThrowStatement): void {
        const thrown = node.argument;
        if (thrown.type !== AST_NODE_TYPES.NewExpression) {
          return;
        }

        const constructorName = errorConstructorName(thrown.callee);
        if (
          constructorName === undefined ||
          !ERROR_NAME_PATTERN.test(constructorName)
        ) {
          return;
        }

        const caught = findEnclosingCatchParam(node);
        if (caught === undefined) {
          return;
        }

        for (const argument of thrown.arguments) {
          if (referencesName(argument, caught.name)) {
            return;
          }
        }

        context.report({
          node: thrown,
          messageId: "missingCause",
          data: { caught: caught.name },
        });
      },
    };
  },
});
