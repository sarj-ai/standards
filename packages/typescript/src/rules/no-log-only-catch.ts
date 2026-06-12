/**
 * @fileoverview Disallow `catch` clauses that only log (via `console.*`) or do
 * nothing and then swallow the error. A catch that logs and falls through —
 * with no `throw`, no `return`, and no real recovery — hides failures: the
 * program keeps running in a broken state while the only signal is a log line
 * that is easy to miss. Either rethrow the error or handle it for real.
 *
 * This rule is deliberately conservative: it flags ONLY catches whose body is
 * empty or consists exclusively of `console.log/error/warn/info/debug` call
 * statements. Any other statement (a `throw`, a `return`, a fallback
 * assignment, a non-console call, etc.) means the catch is doing something and
 * is left alone — we prefer a false negative over a false positive.
 *
 * Test files opt out by default (filenames containing `.test.`, `.spec.`, or a
 * `__tests__/` path segment) since swallow-and-log is common and acceptable in
 * test scaffolding.
 */

import { ESLintUtils, type TSESTree } from "@typescript-eslint/utils";

type MessageIds = "noLogOnlyCatch";
type Options = readonly [];

const DEFAULT_IGNORE_PATTERNS: readonly RegExp[] = [
  /\.test\./,
  /\.spec\./,
  /[\\/]__tests__[\\/]/,
];

const CONSOLE_METHODS: ReadonlySet<string> = new Set([
  "log",
  "error",
  "warn",
  "info",
  "debug",
]);

/**
 * True when a statement is exactly a bare `console.<method>(...)` call, e.g.
 * `console.error(err);`. Anything else (other objects, optional chaining on a
 * non-`console` base, awaited/returned calls, etc.) returns false so the catch
 * is treated as doing real work.
 */
function isConsoleCallStatement(statement: TSESTree.Statement): boolean {
  if (statement.type !== "ExpressionStatement") {
    return false;
  }
  const expr = statement.expression;
  if (expr.type !== "CallExpression") {
    return false;
  }
  const callee = expr.callee;
  if (callee.type !== "MemberExpression") {
    return false;
  }
  const { object, property } = callee;
  if (object.type !== "Identifier" || object.name !== "console") {
    return false;
  }
  if (callee.computed) {
    // console["log"](...) — not a plain identifier method; be conservative.
    return false;
  }
  if (property.type !== "Identifier") {
    return false;
  }
  return CONSOLE_METHODS.has(property.name);
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
        "Disallow `catch` clauses that only log (or do nothing) and then swallow the error; rethrow or handle it instead.",
    },
    schema: [],
    messages: {
      noLogOnlyCatch:
        "Logging then swallowing the error hides failures. Rethrow the error or handle it for real.",
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

        // Empty catch: swallows the error silently.
        if (statements.length === 0) {
          context.report({ node, messageId: "noLogOnlyCatch" });
          return;
        }

        // Flag only if EVERY statement is a bare console.* call. Any other
        // statement (throw, return, fallback, real handler, etc.) means the
        // catch is doing something — leave it alone.
        const everyStatementIsConsoleLog = statements.every((statement) =>
          isConsoleCallStatement(statement),
        );

        if (everyStatementIsConsoleLog) {
          context.report({ node, messageId: "noLogOnlyCatch" });
        }
      },
    };
  },
});
