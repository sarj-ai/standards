/**
 * @fileoverview Flag a template literal with interpolation passed as the message
 * to a logging call — the TypeScript analog of Python SARJ017 (no-fstring-in-log).
 *
 * The house logging style is structured: pass variables as fields so log
 * aggregators can index and filter on them, and so the message template stays
 * constant across calls:
 *
 *     // flagged
 *     logger.info(`call ${callId} finished in ${elapsed}s`);
 *
 *     // preferred
 *     logger.info("call finished", { callId, elapsed });
 *
 * Interpolation bakes the values into the message text, defeating structured
 * search and breaking template grouping.
 *
 * To keep false positives near zero we require BOTH a logger-like receiver
 * (`console`, `logger`/`log`/`_log`/`_logger` and aliases, resolved through a
 * property chain and through `.with(...)`/`.bind(...)`/`getLogger(...)`/
 * `createLogger(...)` builder/factory forms) AND a logging method name. A
 * template literal handed to some unrelated `.info(...)` — a response object, a
 * catalog, `db.query(`... ${x}`)` — is not flagged. A template literal with no
 * `${}` interpolation is never flagged.
 */

import { ESLintUtils, type TSESTree } from "@typescript-eslint/utils";

type MessageIds = "noTemplateLiteralInLog";
type Options = readonly [];

const LOG_METHODS: ReadonlySet<string> = new Set([
  "debug",
  "info",
  "warn",
  "warning",
  "error",
  "exception",
  "critical",
  "trace",
  "log",
  "fatal",
  "success",
]);

const LOGGER_NAMES: ReadonlySet<string> = new Set([
  "console",
  "logger",
  "log",
  "_log",
  "_logger",
]);

const LOGGER_FACTORIES: ReadonlySet<string> = new Set([
  "getlogger",
  "createlogger",
]);

/**
 * True when `node` evaluates to a logger. Mirrors Python `is_logger_expr`:
 * resolves the whole receiver chain so builder/factory forms are recognised —
 * `logger.bind(...).info(...)`, `logger.with(...).warn(...)`,
 * `getLogger(name).error(...)`, `this.logger.debug(...)`.
 */
function looksLikeLogger(node: TSESTree.Node): boolean {
  switch (node.type) {
    case "Identifier": {
      const name = node.name.toLowerCase();
      return LOGGER_NAMES.has(name) || LOGGER_FACTORIES.has(name);
    }
    case "MemberExpression": {
      if (!node.computed && node.property.type === "Identifier") {
        const prop = node.property.name.toLowerCase();
        if (LOGGER_NAMES.has(prop) || LOGGER_FACTORIES.has(prop)) {
          return true;
        }
      }
      return looksLikeLogger(node.object);
    }
    case "CallExpression":
      return looksLikeLogger(node.callee);
    default:
      return false;
  }
}

/**
 * Find an interpolating template literal in `node`, descending `+`-concat
 * operands. A concatenated message like `` `${x}` + "!" `` wraps the template in
 * a BinaryExpression, so the interpolation is not the top-level node. A template
 * literal with no `${}` (`.expressions.length === 0`) is left unflagged.
 */
function findInterpolatingTemplate(
  node: TSESTree.Expression | TSESTree.PrivateIdentifier,
): TSESTree.TemplateLiteral | null {
  if (node.type === "TemplateLiteral") {
    return node.expressions.length > 0 ? node : null;
  }
  if (node.type === "BinaryExpression" && node.operator === "+") {
    return (
      findInterpolatingTemplate(node.left) ??
      findInterpolatingTemplate(node.right)
    );
  }
  return null;
}

/**
 * Index of the message argument. The level-first `logger.log(level, msg)` form
 * (loguru / winston) puts the message at arg[1]; every other method — and
 * `console.log(msg, ...values)`, whose first argument IS the message — puts it
 * at arg[0].
 */
function messageArg(
  node: TSESTree.CallExpression,
  method: string,
  receiver: TSESTree.Expression,
): TSESTree.Expression | null {
  const levelFirst = method === "log" && !isConsoleReceiver(receiver);
  const arg = node.arguments[levelFirst ? 1 : 0];
  if (arg === undefined || arg.type === "SpreadElement") {
    return null;
  }
  return arg;
}

function isConsoleReceiver(node: TSESTree.Expression): boolean {
  return node.type === "Identifier" && node.name === "console";
}

export default ESLintUtils.RuleCreator(
  (name) =>
    `https://github.com/sarj-ai/standards/blob/main/packages/typescript/src/rules/${name}.ts`,
)<Options, MessageIds>({
  name: "no-template-literal-in-log",
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow an interpolating template literal as a logging message — pass variables as structured fields so logs stay filterable and templates stay constant.",
    },
    schema: [],
    messages: {
      noTemplateLiteralInLog:
        "Interpolating template literal as a logging message — pass variables as structured fields (logger.info('msg', { key })) instead.",
    },
  },
  defaultOptions: [],
  create(context) {
    return {
      CallExpression(node: TSESTree.CallExpression): void {
        const callee = node.callee;
        if (callee.type !== "MemberExpression" || callee.computed) {
          return;
        }
        if (callee.property.type !== "Identifier") {
          return;
        }
        const method = callee.property.name;
        if (!LOG_METHODS.has(method)) {
          return;
        }
        if (!looksLikeLogger(callee.object)) {
          return;
        }
        const arg = messageArg(node, method, callee.object);
        if (arg === null) {
          return;
        }
        if (findInterpolatingTemplate(arg) !== null) {
          context.report({ node, messageId: "noTemplateLiteralInLog" });
        }
      },
    };
  },
});
