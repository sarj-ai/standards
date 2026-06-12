/**
 * @fileoverview Disallow `await` expressions located directly inside the body
 * of a `for` / `for-of` / `for-in` / `while` loop within the same function
 * scope. Awaiting serially inside a loop serializes I/O that is often better
 * expressed as `await Promise.all(xs.map(async (x) => ...))`, letting the
 * operations run concurrently.
 *
 * This rule is intentionally conservative — it prefers a false negative over a
 * false positive:
 *   - `for await...of` is NOT flagged (async iteration is the correct tool).
 *   - awaits inside a function/arrow defined within the loop are NOT flagged
 *     (they belong to a different function scope).
 *   - awaits not inside any loop are NOT flagged.
 * At most one report is emitted per offending loop.
 */

import { ESLintUtils, type TSESTree } from "@typescript-eslint/utils";

type MessageIds = "noSequentialAwait";
type Options = readonly [];

/**
 * Node types that introduce a new function scope. We never descend across one
 * of these when looking for awaits belonging to a loop, because an `await`
 * inside a nested function/arrow is awaited by *that* function, not by the loop.
 */
function isFunctionLike(node: TSESTree.Node): boolean {
  return (
    node.type === "FunctionDeclaration" ||
    node.type === "FunctionExpression" ||
    node.type === "ArrowFunctionExpression"
  );
}

/**
 * Loop node types whose bodies we scan. `ForOfStatement` is handled specially
 * by the caller so that `for await...of` is excluded.
 */
type LoopNode =
  | TSESTree.ForStatement
  | TSESTree.ForOfStatement
  | TSESTree.ForInStatement
  | TSESTree.WhileStatement
  | TSESTree.DoWhileStatement;

/**
 * Statement node types that introduce a nested loop. When scanning a loop's
 * body we must NOT descend into another loop — that inner loop's awaits belong
 * to it and are reported when the inner loop is visited. This keeps reporting
 * at one-per-loop and avoids double-flagging an outer loop for an await that
 * only appears inside a nested loop.
 */
function isLoop(node: TSESTree.Node): boolean {
  return (
    node.type === "ForStatement" ||
    node.type === "ForOfStatement" ||
    node.type === "ForInStatement" ||
    node.type === "WhileStatement" ||
    node.type === "DoWhileStatement"
  );
}

export default ESLintUtils.RuleCreator(
  (name) =>
    `https://github.com/sarj-ai/linting/blob/main/packages/typescript/src/rules/${name}.ts`,
)<Options, MessageIds>({
  name: "no-sequential-await",
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow serial `await` inside a loop; use `await Promise.all(...)` to run the operations concurrently.",
    },
    schema: [],
    messages: {
      noSequentialAwait:
        "Avoid `await` inside a loop — it serializes I/O. Collect the promises and `await Promise.all(xs.map(async (x) => ...))` instead.",
    },
  },
  defaultOptions: [],
  create(context) {
    /**
     * Walks the subtree rooted at `node`, returning the first `AwaitExpression`
     * that belongs to *this* loop's scope — i.e. reachable without crossing a
     * nested function/arrow boundary or descending into a nested loop. Returns
     * `null` if none.
     *
     * Stopping at function boundaries excludes awaits in nested functions
     * (awaited by that function, not the loop). Stopping at nested-loop
     * boundaries means each loop only "owns" its own direct awaits, so an outer
     * loop isn't flagged for an await that lives solely in an inner loop, and
     * every report stays one-per-loop.
     */
    function findAwaitInScope(
      node: TSESTree.Node,
    ): TSESTree.AwaitExpression | null {
      if (node.type === "AwaitExpression") {
        return node;
      }
      if (isFunctionLike(node)) {
        // Crossing into a different function scope — its awaits aren't ours.
        return null;
      }

      for (const key of Object.keys(node) as (keyof TSESTree.Node)[]) {
        if (key === "parent") {
          continue;
        }
        const value = node[key];
        if (Array.isArray(value)) {
          for (const child of value) {
            if (isNode(child) && !isLoop(child)) {
              const found = findAwaitInScope(child);
              if (found) {
                return found;
              }
            }
          }
        } else if (isNode(value) && !isLoop(value)) {
          const found = findAwaitInScope(value);
          if (found) {
            return found;
          }
        }
      }

      return null;
    }

    function isNode(value: unknown): value is TSESTree.Node {
      return (
        typeof value === "object" &&
        value !== null &&
        typeof (value as { type?: unknown }).type === "string"
      );
    }

    /**
     * Reports the loop if its body contains an `await` belonging to the same
     * function scope. The loop's `body` (and, for the C-style `for`, its init /
     * test / update expressions) are the only places an "await in this loop"
     * can live; awaits in a *nested* loop are caught when that nested loop is
     * itself visited, keeping reports at one-per-loop.
     */
    function checkLoop(node: LoopNode): void {
      const parts: (TSESTree.Node | null)[] = [node.body];

      if (node.type === "ForStatement") {
        parts.push(node.init, node.test, node.update);
      } else if (
        node.type === "ForOfStatement" ||
        node.type === "ForInStatement"
      ) {
        parts.push(node.right);
      } else {
        // While / DoWhile.
        parts.push(node.test);
      }

      for (const part of parts) {
        // A part that is itself a loop (e.g. `for (...) for (...) await f()`)
        // is owned by that inner loop and checked when it is visited.
        if (part && !isLoop(part) && findAwaitInScope(part)) {
          context.report({ node, messageId: "noSequentialAwait" });
          return;
        }
      }
    }

    return {
      ForStatement: checkLoop,
      ForInStatement: checkLoop,
      WhileStatement: checkLoop,
      DoWhileStatement: checkLoop,
      ForOfStatement(node: TSESTree.ForOfStatement): void {
        // `for await...of` is correct async iteration — never flag it.
        if (node.await) {
          return;
        }
        checkLoop(node);
      },
    };
  },
});
