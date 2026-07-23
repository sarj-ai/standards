/**
 * @fileoverview Disallow `catch` clauses that only log (via `console.*` or a
 * logger receiver such as `logger.warn(...)` / `Log.error(...)`) and then
 * swallow the error. A catch that logs and falls through — with no `throw`, no
 * `return`, and no real recovery — hides failures: the program keeps running in
 * a broken state while the only signal is a log line that is easy to miss.
 * Either rethrow the error or handle it for real.
 *
 * This rule is deliberately conservative and fires in exactly two shapes:
 *   - `noLogOnlyCatch`: the catch body is non-empty and *every* statement is a
 *     logging call (`console.*` or a call on a logger-named receiver). Any other
 *     statement (a `throw`, a `return`, a fallback assignment, a non-logging
 *     call, etc.) means the catch is doing something and is left alone.
 *   - `emptyCatch`: the catch body is genuinely empty AND carries no comment.
 *     A comment-only catch (`catch { /* ignore, safe because … *\/ }`) is treated
 *     as an intentional, documented ignore and is exempt.
 *
 * A previous version fired the "logging then swallowing" message on empty and
 * comment-only catches that contained no logging call at all — the vast majority
 * of real-world hits — which was factually wrong. The two distinct message ids
 * keep each diagnostic accurate.
 *
 * Test files opt out by default (filenames containing `.test.`, `.spec.`, or a
 * `__tests__/` path segment) since swallow-and-log is common and acceptable in
 * test scaffolding.
 */

import { ESLintUtils, type TSESTree } from "@typescript-eslint/utils";

import { isLoggingCall } from "./_logging.js";

type MessageIds = "noLogOnlyCatch" | "emptyCatch";
type Options = readonly [];

const DEFAULT_IGNORE_PATTERNS: readonly RegExp[] = [
  /\.test\./,
  /\.spec\./,
  /[\\/]__tests__[\\/]/,
];

/** True when a statement is exactly a bare logging call, e.g. `console.error(err);` or `logger.warn(err);`. */
function isLoggingCallStatement(statement: TSESTree.Statement): boolean {
  if (statement.type !== "ExpressionStatement") {
    return false;
  }
  return isLoggingCall(statement.expression);
}

export default ESLintUtils.RuleCreator(
  (name) =>
    `https://github.com/sarj-ai/linting/blob/main/packages/typescript/src/rules/${name}.ts`,
)<Options, MessageIds>({
  name: "no-log-only-catch",
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow `catch` clauses that only log (or silently do nothing) and then swallow the error; rethrow or handle it instead.",
    },
    schema: [],
    messages: {
      noLogOnlyCatch:
        "Logging then swallowing the error hides failures. Rethrow the error or handle it for real.",
      emptyCatch:
        "Empty catch silently swallows the error. Rethrow it, handle it, or add a comment explaining why it is safe to ignore.",
    },
  },
  defaultOptions: [],
  create(context) {
    const filename = context.filename;

    const isIgnoredByDefault = DEFAULT_IGNORE_PATTERNS.some((re) =>
      re.test(filename),
    );

    if (isIgnoredByDefault) {
      return {};
    }

    return {
      CatchClause(node: TSESTree.CatchClause): void {
        const statements = node.body.body;

        if (statements.length === 0) {
          // A comment inside the block documents an intentional ignore; only a
          // truly empty catch is an unexplained silent swallow.
          if (context.sourceCode.getCommentsInside(node.body).length > 0) {
            return;
          }
          context.report({ node, messageId: "emptyCatch" });
          return;
        }

        const everyStatementIsLogging = statements.every((statement) =>
          isLoggingCallStatement(statement),
        );

        if (everyStatementIsLogging) {
          context.report({ node, messageId: "noLogOnlyCatch" });
        }
      },
    };
  },
});
