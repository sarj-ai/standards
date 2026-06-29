/**
 * @fileoverview Disallow using `Math.random()` to generate identifiers,
 * tokens, keys, or other security-sensitive values. `Math.random()` is not
 * cryptographically secure and is predictable — using it for IDs/tokens/secrets
 * can lead to collisions and trivially guessable values. Prefer
 * `crypto.randomUUID()` or `crypto.getRandomValues(...)` instead.
 *
 * The rule is intentionally conservative and only flags two precise patterns:
 *   1. A `Math.random()` result fed into a `.toString(36)` chain — the classic
 *      insecure random-id idiom (e.g. `Math.random().toString(36).slice(2)`).
 *   2. A `Math.random()` call whose nearest enclosing binding or property NAME
 *      looks identifier/secret-like (matches `/id|token|key|secret|uuid|nonce|
 *      session|password|salt/i`).
 *
 * Bare `Math.random()` used for non-identifier purposes (jitter, sampling,
 * rolls, etc.) is NOT flagged.
 *
 * KNOWN GAP (false-negative): an arithmetic expression between `Math.random()`
 * and `.toString(36)` breaks the member-chain walk, e.g.
 * `(Math.random() * 1e9).toString(36)`. The intervening `BinaryExpression`
 * means `Math.random()` is no longer the object end of the `.toString` chain,
 * so trigger 1 does not fire. Such code is only caught if its binding/property
 * name looks identifier/secret-like (trigger 2). See the documented test case.
 */

import { ESLintUtils, type TSESTree } from "@typescript-eslint/utils";

type MessageIds = "insecureRandomId";
type Options = readonly [];

const NAME_PATTERN = /id|token|key|secret|uuid|nonce|session|password|salt/i;

/**
 * Returns true if `node` is a `Math.random()` CallExpression.
 */
function isMathRandomCall(node: TSESTree.Node): node is TSESTree.CallExpression {
  if (node.type !== "CallExpression") {
    return false;
  }
  const callee = node.callee;
  if (callee.type !== "MemberExpression" || callee.computed) {
    return false;
  }
  const { object, property } = callee;
  return (
    object.type === "Identifier" &&
    object.name === "Math" &&
    property.type === "Identifier" &&
    property.name === "random"
  );
}

/**
 * Returns true if `node` (a `Math.random()` call) is the base of a member
 * chain that calls `.toString(36)` somewhere above it, e.g.
 * `Math.random().toString(36)` or `Math.random().toString(36).slice(2)`.
 */
function isPartOfToString36Chain(node: TSESTree.Node): boolean {
  let current: TSESTree.Node = node;
  let parent = current.parent;

  while (parent) {
    if (
      parent.type === "MemberExpression" &&
      parent.object === current &&
      !parent.computed &&
      parent.property.type === "Identifier" &&
      parent.property.name === "toString"
    ) {
      // The MemberExpression `<current>.toString` should be called with a
      // radix argument of `36`.
      const grandparent = parent.parent;
      if (
        grandparent &&
        grandparent.type === "CallExpression" &&
        grandparent.callee === parent
      ) {
        const firstArg = grandparent.arguments[0];
        if (
          firstArg &&
          firstArg.type === "Literal" &&
          firstArg.value === 36
        ) {
          return true;
        }
      }
    }

    // Keep walking up only while we remain the "object" of a member/call
    // chain. If we are anything other than the object end of the chain, the
    // `.toString(36)` (if any) does not apply to this `Math.random()`.
    if (
      parent.type === "MemberExpression" &&
      parent.object === current
    ) {
      current = parent;
      parent = current.parent;
      continue;
    }
    if (parent.type === "CallExpression" && parent.callee === current) {
      current = parent;
      parent = current.parent;
      continue;
    }
    break;
  }

  return false;
}

/**
 * Walks up from `node` to find the name of the nearest enclosing binding
 * (VariableDeclarator id) or property (Property / PropertyDefinition key),
 * and returns it. Returns `undefined` if no such name is found before leaving
 * the enclosing initializer/value context.
 */
function findEnclosingName(node: TSESTree.Node): string | undefined {
  let current: TSESTree.Node = node;
  let parent = current.parent;

  while (parent) {
    // const sessionToken = Math.random()...
    if (parent.type === "VariableDeclarator" && parent.init === current) {
      if (parent.id.type === "Identifier") {
        return parent.id.name;
      }
      return undefined;
    }

    // { sessionToken: Math.random()... }
    if (parent.type === "Property" && parent.value === current) {
      const key = parent.key;
      if (!parent.computed && key.type === "Identifier") {
        return key.name;
      }
      if (key.type === "Literal" && typeof key.value === "string") {
        return key.value;
      }
      return undefined;
    }

    // class { sessionToken = Math.random()...; }
    if (parent.type === "PropertyDefinition" && parent.value === current) {
      const key = parent.key;
      if (!parent.computed && key.type === "Identifier") {
        return key.name;
      }
      if (key.type === "Literal" && typeof key.value === "string") {
        return key.value;
      }
      return undefined;
    }

    // Stop walking once we cross a boundary where the name no longer reflects
    // a binding/property whose value is being initialized.
    if (
      parent.type === "FunctionDeclaration" ||
      parent.type === "FunctionExpression" ||
      parent.type === "ArrowFunctionExpression" ||
      parent.type === "BlockStatement" ||
      parent.type === "ReturnStatement" ||
      parent.type === "ExpressionStatement"
    ) {
      return undefined;
    }

    current = parent;
    parent = current.parent;
  }

  return undefined;
}

export default ESLintUtils.RuleCreator(
  (name) =>
    `https://github.com/sarj-ai/linting/blob/main/packages/typescript/src/rules/${name}.ts`,
)<Options, MessageIds>({
  name: "no-insecure-random-id",
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow using `Math.random()` to generate identifiers, tokens, or secrets; use `crypto.randomUUID()` or `crypto.getRandomValues(...)` instead.",
    },
    schema: [],
    messages: {
      insecureRandomId:
        "`Math.random()` is not cryptographically secure and is predictable; do not use it to generate IDs, tokens, or secrets. Use `crypto.randomUUID()` or `crypto.getRandomValues(...)` instead.",
    },
  },
  defaultOptions: [],
  create(context) {
    return {
      CallExpression(node: TSESTree.CallExpression): void {
        if (!isMathRandomCall(node)) {
          return;
        }

        // Trigger 1: classic `.toString(36)` insecure id idiom.
        if (isPartOfToString36Chain(node)) {
          context.report({ node, messageId: "insecureRandomId" });
          return;
        }

        // Trigger 2: enclosing binding/property name looks id/secret-like.
        const name = findEnclosingName(node);
        if (name !== undefined && NAME_PATTERN.test(name)) {
          context.report({ node, messageId: "insecureRandomId" });
        }
      },
    };
  },
});
