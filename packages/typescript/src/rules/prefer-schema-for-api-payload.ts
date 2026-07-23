/**
 * @fileoverview Don't access `response.json()` fields without a Zod parse first.
 *
 * Pattern flagged:
 *   const data = await response.json();
 *   doSomething(data.foo);  // <-- unvalidated property access
 *
 * Encouraged:
 *   const data = MySchema.parse(await response.json());
 *   doSomething(data.foo);  // typed + validated
 *
 * Heuristic:
 *   - Track variables initialized to `await someCall.json()` using ESLint's scope manager.
 *   - Untrack if reassigned to anything other than another raw `json()` call.
 *   - Untrack when passed to a user-defined type-guard predicate — a call whose
 *     callee name matches `/^is[A-Z]/`, or any call used in an `if`/`?:` test
 *     position (`if (guard(body)) { … body.foo … }`). Hand-written guards validate
 *     the payload just as a Zod `.parse()` does.
 *   - Flag MemberExpression reads and destructuring off tracked variables.
 *   - `.parse()` / `.safeParse()` chained directly on the json call are legit
 *     and never produce a tracked binding in the first place.
 *
 * References:
 *   - https://zod.dev/?id=parse
 *   - https://www.totaltypescript.com/parse-don-t-validate
 */

import {
  AST_NODE_TYPES,
  ESLintUtils,
  type TSESTree,
} from "@typescript-eslint/utils";
import type { RuleContext, Scope } from "@typescript-eslint/utils/ts-eslint";

type MessageIds = "unparsedJsonAccess";
type Options = readonly [];

type Ctx = Readonly<RuleContext<MessageIds, Options>>;

/**
 * Peel TypeScript wrapper nodes that don't affect the underlying value
 * (`as Foo`, `<Foo>x`, `x!`, `x satisfies Foo`, parentheses, optional chain
 * wrappers). Returns the inner expression we actually care about.
 */
const unwrap = (
  node: TSESTree.Node | null | undefined,
): TSESTree.Node | null => {
  let current: TSESTree.Node | null | undefined = node;
  while (current !== null && current !== undefined) {
    if (
      current.type === AST_NODE_TYPES.TSAsExpression ||
      current.type === AST_NODE_TYPES.TSTypeAssertion ||
      current.type === AST_NODE_TYPES.TSNonNullExpression ||
      current.type === AST_NODE_TYPES.TSSatisfiesExpression
    ) {
      current = current.expression;
    } else if (current.type === AST_NODE_TYPES.ChainExpression) {
      current = current.expression;
    } else {
      break;
    }
  }
  return current ?? null;
};

/**
 * Returns true if the expression is (optionally awaited) `<x>.json()`.
 */
const isJsonCall = (
  node: TSESTree.Node | null | undefined,
): boolean => {
  let current = unwrap(node);
  if (current === null) return false;
  if (current.type === AST_NODE_TYPES.AwaitExpression) {
    current = unwrap(current.argument);
  }
  if (current === null || current.type !== AST_NODE_TYPES.CallExpression) {
    return false;
  }
  const callee = unwrap(current.callee);
  if (callee === null || callee.type !== AST_NODE_TYPES.MemberExpression) {
    return false;
  }
  const property = unwrap(callee.property);
  return (
    property !== null &&
    property.type === AST_NODE_TYPES.Identifier &&
    property.name === "json"
  );
};

const findVariable = (
  scope: Scope.Scope | null,
  name: string,
): Scope.Variable | null => {
  let current: Scope.Scope | null = scope;
  while (current !== null) {
    const variable = current.set.get(name);
    if (variable !== undefined) return variable;
    current = current.upper;
  }
  return null;
};

/** User-defined type-guard predicate names, e.g. `isProtectedResourceMetadata`. */
const GUARD_NAME_RE = /^is[A-Z]/;

/**
 * True when a call sits in a boolean-test position (`if`/`while`/`for`/`?:`),
 * seen through `!`, `&&`/`||`, and optional-chaining wrappers — i.e. it narrows.
 */
const isGuardTestPosition = (node: TSESTree.Node): boolean => {
  let current: TSESTree.Node = node;
  let parent: TSESTree.Node | null | undefined = current.parent;
  while (parent !== undefined && parent !== null) {
    switch (parent.type) {
      case AST_NODE_TYPES.UnaryExpression:
      case AST_NODE_TYPES.LogicalExpression:
      case AST_NODE_TYPES.ChainExpression:
        current = parent;
        parent = parent.parent;
        continue;
      case AST_NODE_TYPES.IfStatement:
      case AST_NODE_TYPES.ConditionalExpression:
      case AST_NODE_TYPES.WhileStatement:
      case AST_NODE_TYPES.DoWhileStatement:
      case AST_NODE_TYPES.ForStatement:
        return parent.test === current;
      default:
        return false;
    }
  }
  return false;
};

const isUnvalidatedVariableRef = (
  node: TSESTree.Node | null | undefined,
  scope: Scope.Scope,
  tracked: ReadonlySet<Scope.Variable>,
): boolean => {
  const unwrapped = unwrap(node);
  if (unwrapped === null || unwrapped.type !== AST_NODE_TYPES.Identifier) {
    return false;
  }
  const variable = findVariable(scope, unwrapped.name);
  return variable !== null && tracked.has(variable);
};

export default ESLintUtils.RuleCreator(
  (name) =>
    `https://github.com/sarj-ai/linting/blob/main/packages/typescript/src/rules/${name}.ts`,
)<Options, MessageIds>({
  name: "prefer-schema-for-api-payload",
  meta: {
    type: "problem",
    docs: {
      description:
        "Require Zod (or similar) schema validation on `response.json()` before property access.",
    },
    schema: [],
    messages: {
      unparsedJsonAccess:
        "Property access on the result of `response.json()` without a schema parse. Pipe through `XSchema.parse(...)` (Zod) before reading fields.",
    },
  },
  defaultOptions: [],
  create(context: Ctx) {
    const unvalidatedVariables = new Set<Scope.Variable>();

    const trackInitializer = (
      declarator: TSESTree.VariableDeclarator,
    ): void => {
      if (!isJsonCall(declarator.init)) return;
      const declaredVars = context.sourceCode.getDeclaredVariables(declarator);
      const variable = declaredVars[0];
      if (variable !== undefined) {
        unvalidatedVariables.add(variable);
      }
    };

    return {
      VariableDeclarator(node): void {
        const scope = context.sourceCode.getScope(node);

        if (node.id.type === AST_NODE_TYPES.Identifier) {
          trackInitializer(node);
          return;
        }

        if (
          node.id.type === AST_NODE_TYPES.ObjectPattern ||
          node.id.type === AST_NODE_TYPES.ArrayPattern
        ) {
          if (isJsonCall(node.init)) {
            context.report({ node: node.id, messageId: "unparsedJsonAccess" });
            return;
          }
          if (
            isUnvalidatedVariableRef(node.init, scope, unvalidatedVariables)
          ) {
            context.report({ node: node.id, messageId: "unparsedJsonAccess" });
          }
        }
      },
      AssignmentExpression(node): void {
        const scope = context.sourceCode.getScope(node);

        if (node.left.type === AST_NODE_TYPES.Identifier) {
          const variable = findVariable(scope, node.left.name);
          if (variable === null) return;
          if (isJsonCall(node.right)) {
            unvalidatedVariables.add(variable);
          } else {
            // Reassigned to a parse call or something else: drop tracking.
            unvalidatedVariables.delete(variable);
          }
          return;
        }

        if (
          node.left.type === AST_NODE_TYPES.ObjectPattern ||
          node.left.type === AST_NODE_TYPES.ArrayPattern
        ) {
          if (isJsonCall(node.right)) {
            context.report({
              node: node.left,
              messageId: "unparsedJsonAccess",
            });
            return;
          }
          if (
            isUnvalidatedVariableRef(node.right, scope, unvalidatedVariables)
          ) {
            context.report({
              node: node.left,
              messageId: "unparsedJsonAccess",
            });
          }
        }
      },
      CallExpression(node): void {
        if (node.callee.type !== AST_NODE_TYPES.Identifier) return;
        if (!GUARD_NAME_RE.test(node.callee.name) && !isGuardTestPosition(node)) {
          return;
        }
        const scope = context.sourceCode.getScope(node);
        for (const arg of node.arguments) {
          if (arg.type === AST_NODE_TYPES.SpreadElement) continue;
          const unwrapped = unwrap(arg);
          if (unwrapped === null || unwrapped.type !== AST_NODE_TYPES.Identifier) {
            continue;
          }
          const variable = findVariable(scope, unwrapped.name);
          if (variable !== null) unvalidatedVariables.delete(variable);
        }
      },
      MemberExpression(node): void {
        const scope = context.sourceCode.getScope(node);
        const obj = unwrap(node.object);

        if (isJsonCall(obj)) {
          // Direct `.foo` access on `(await r.json()).foo` is always bad,
          // unless the parent call is a `.parse()`/`.safeParse()` — in which
          // case it's a validation, not an unvalidated read.
          const parent = node.parent;
          if (
            parent.type === AST_NODE_TYPES.CallExpression &&
            parent.callee === node &&
            node.property.type === AST_NODE_TYPES.Identifier &&
            (node.property.name === "parse" ||
              node.property.name === "safeParse")
          ) {
            return;
          }
          context.report({ node, messageId: "unparsedJsonAccess" });
          return;
        }

        if (
          obj !== null &&
          obj.type === AST_NODE_TYPES.Identifier &&
          isUnvalidatedVariableRef(obj, scope, unvalidatedVariables)
        ) {
          context.report({ node, messageId: "unparsedJsonAccess" });
          const variable = findVariable(scope, obj.name);
          if (variable !== null) {
            unvalidatedVariables.delete(variable);
          }
        }
      },
    };
  },
});
