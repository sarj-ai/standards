import * as tsParser from "@typescript-eslint/parser";
import { RuleTester } from "@typescript-eslint/rule-tester";
import { afterAll, describe, it } from "vitest";

import rule from "../../src/rules/no-template-literal-in-log.js";

RuleTester.afterAll = afterAll;
RuleTester.describe = describe;
RuleTester.it = it;
RuleTester.itOnly = it.only;

const ruleTester = new RuleTester({
  languageOptions: {
    parser: tsParser,
  },
});

ruleTester.run("no-template-literal-in-log", rule, {
  valid: [
    // Template literal with no interpolation — a constant message.
    { code: "logger.info(`static message`);" },
    // Plain string literal message.
    { code: 'logger.info("plain message");' },
    // Structured logging: constant message + fields object.
    { code: "logger.info(`finished`, { callId, elapsed });" },
    // Non-logger receiver named `resp` with an `.info` method.
    { code: "resp.info(`status ${code}`);" },
    // Non-logger receiver `response`.
    { code: "response.error(`bad ${x}`);" },
    // Non-logger receiver `catalog`.
    { code: "catalog.info(`item ${id}`);" },
    // A SQL query builder — not a logger, must not fire on interpolated SQL.
    { code: "db.query(`SELECT * FROM t WHERE id = ${id}`);" },
    // Tagged template on a query — not a plain TemplateLiteral argument.
    { code: "db.query(sql`SELECT * FROM t WHERE id = ${id}`);" },
    // Logger method but the message is a plain string; interpolation elsewhere.
    { code: "logger.info('done', { detail: `x ${y}` });" },
    // logger.log with a non-interpolating template as the message (arg[1]).
    { code: "logger.log(level, `static`);" },
    // Computed logging method access — treated conservatively.
    { code: "logger['info'](`x ${y}`);" },
    // console.log's message is arg[0]: a constant label with a template VALUE
    // as a later argument must not fire (regression: noura NouraApiClient).
    { code: "console.log('[api] request to:', `${base}/v1/auth`);" },
  ],
  invalid: [
    {
      code: "logger.info(`x=${y}`);",
      errors: [{ messageId: "noTemplateLiteralInLog" }],
    },
    {
      code: "logger.debug(`x=${y}`);",
      errors: [{ messageId: "noTemplateLiteralInLog" }],
    },
    {
      code: "logger.warn(`x=${y}`);",
      errors: [{ messageId: "noTemplateLiteralInLog" }],
    },
    {
      code: "logger.warning(`x=${y}`);",
      errors: [{ messageId: "noTemplateLiteralInLog" }],
    },
    {
      code: "logger.error(`x=${y}`);",
      errors: [{ messageId: "noTemplateLiteralInLog" }],
    },
    {
      code: "logger.exception(`x=${y}`);",
      errors: [{ messageId: "noTemplateLiteralInLog" }],
    },
    {
      code: "logger.critical(`x=${y}`);",
      errors: [{ messageId: "noTemplateLiteralInLog" }],
    },
    {
      code: "logger.trace(`x=${y}`);",
      errors: [{ messageId: "noTemplateLiteralInLog" }],
    },
    {
      code: "logger.fatal(`x=${y}`);",
      errors: [{ messageId: "noTemplateLiteralInLog" }],
    },
    {
      code: "logger.success(`x=${y}`);",
      errors: [{ messageId: "noTemplateLiteralInLog" }],
    },
    // console receiver.
    {
      code: "console.error(`${e}`);",
      errors: [{ messageId: "noTemplateLiteralInLog" }],
    },
    // logger.log(level, msg) — message is arg[1].
    {
      code: "logger.log(level, `${x}`);",
      errors: [{ messageId: "noTemplateLiteralInLog" }],
    },
    // Property chain ending in a logger name.
    {
      code: "this.logger.info(`x=${y}`);",
      errors: [{ messageId: "noTemplateLiteralInLog" }],
    },
    // Builder chain: .bind(...) on a logger.
    {
      code: "logger.bind({ a: 1 }).warn(`x=${y}`);",
      errors: [{ messageId: "noTemplateLiteralInLog" }],
    },
    // Builder chain: .with(...) on a logger.
    {
      code: "logger.with({ a: 1 }).info(`x=${y}`);",
      errors: [{ messageId: "noTemplateLiteralInLog" }],
    },
    // Factory chain: getLogger(...).error(...).
    {
      code: "getLogger('mod').error(`x=${y}`);",
      errors: [{ messageId: "noTemplateLiteralInLog" }],
    },
    // Factory chain: createLogger(...).debug(...).
    {
      code: "createLogger().debug(`x=${y}`);",
      errors: [{ messageId: "noTemplateLiteralInLog" }],
    },
    // Case-insensitive logger identifier.
    {
      code: "Logger.info(`x=${y}`);",
      errors: [{ messageId: "noTemplateLiteralInLog" }],
    },
    // `+`-concat wrapping an interpolating template.
    {
      code: "logger.info(`x=${y}` + '!');",
      errors: [{ messageId: "noTemplateLiteralInLog" }],
    },
    // `+`-concat where the template is the right operand.
    {
      code: "logger.error('prefix: ' + `${e}`);",
      errors: [{ messageId: "noTemplateLiteralInLog" }],
    },
  ],
});
