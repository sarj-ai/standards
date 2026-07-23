/**
 * @fileoverview Shared helpers for recognising logging / error-reporting calls.
 * Used by `no-log-only-catch` and `no-sentinel-return-on-catch` so both rules
 * agree on what counts as "the error was logged/reported" before deciding a
 * catch silently swallows it. The logger-name and log-method sets mirror
 * `no-secret-in-log.ts`.
 */

import { type TSESTree } from "@typescript-eslint/utils";

export const LOG_METHODS: ReadonlySet<string> = new Set([
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

export const LOGGER_NAMES: ReadonlySet<string> = new Set([
  "logger",
  "log",
  "logging",
  "loguru",
  "console",
  "_logger",
  "_log",
]);

/**
 * Names of free functions / methods that report an error to a handler or sink,
 * e.g. `onUnexpectedError`, `reportError`, `captureException`, `logError`. Kept
 * broad on purpose: pairing this with "takes the caught binding" is what makes
 * it precise.
 */
export const REPORT_NAME_RE = /error|report|capture|log|trace|warn/i;

/**
 * True when `expr` resolves to a logger receiver — a bare logger identifier
 * (`logger`, `log`, `console`, `Log`) or a member chain ending in one
 * (`this.logger`, `svc.log`).
 */
export function isLoggerReceiver(
  expr: TSESTree.Expression | TSESTree.PrivateIdentifier,
): boolean {
  switch (expr.type) {
    case "Identifier":
      return LOGGER_NAMES.has(expr.name.toLowerCase());
    case "MemberExpression": {
      const { property, object } = expr;
      if (
        !expr.computed &&
        property.type === "Identifier" &&
        LOGGER_NAMES.has(property.name.toLowerCase())
      ) {
        return true;
      }
      return isLoggerReceiver(object);
    }
    default:
      return false;
  }
}

/**
 * True when `expr` is a logging call: `console.error(...)`, `logger.warn(...)`,
 * `Log.error(...)`, `this.logger.info(...)`, etc. Requires a non-computed log
 * method on a logger receiver.
 */
export function isLoggingCall(expr: TSESTree.Expression): boolean {
  if (expr.type !== "CallExpression") {
    return false;
  }
  const callee = expr.callee;
  if (
    callee.type !== "MemberExpression" ||
    callee.computed ||
    callee.property.type !== "Identifier"
  ) {
    return false;
  }
  if (!LOG_METHODS.has(callee.property.name.toLowerCase())) {
    return false;
  }
  return isLoggerReceiver(callee.object);
}

/** The static callee name of a call (free function or method), or null. */
export function calleeName(callee: TSESTree.Node): string | null {
  if (callee.type === "Identifier") {
    return callee.name;
  }
  if (
    callee.type === "MemberExpression" &&
    !callee.computed &&
    callee.property.type === "Identifier"
  ) {
    return callee.property.name;
  }
  return null;
}
