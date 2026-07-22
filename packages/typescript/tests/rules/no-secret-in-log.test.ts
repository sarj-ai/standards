import * as tsParser from "@typescript-eslint/parser";
import { RuleTester } from "@typescript-eslint/rule-tester";
import { afterAll, describe, it } from "vitest";

import rule from "../../src/rules/no-secret-in-log.js";

RuleTester.afterAll = afterAll;
RuleTester.describe = describe;
RuleTester.it = it;
RuleTester.itOnly = it.only;

const ruleTester = new RuleTester({
  languageOptions: {
    parser: tsParser,
  },
});

ruleTester.run("no-secret-in-log", rule, {
  valid: [
    // Innocuous trailing token: usage counter, not the secret.
    { code: 'logger.info("usage", { tokenCount });' },
    // Row-id of a key, not the key material.
    { code: 'logger.info("key", { apiKeyId });' },
    // Discriminator, not the credential.
    { code: 'logger.debug("auth", { tokenType });' },
    // Boolean feature flag, not the credential.
    { code: 'logger.warn("cfg", { passwordEnabled });' },
    // Boolean presence flag.
    { code: 'logger.info("auth", { tokenPresent });' },
    // Redaction markers are the intended safe form.
    { code: 'logger.info("auth", { tokenPrefix });' },
    { code: 'logger.info("auth", { apiKeyTag });' },
    { code: 'logger.info("auth", { passwordHash });' },
    { code: 'logger.info("auth", { tokenLength });' },
    // Non-secret payload.
    { code: 'logger.info("user", { userId });' },
    { code: 'logger.info("req", { requestId, durationMs });' },
    // Non-logger receiver: not a logging call.
    { code: 'metrics.info("x", { token });' },
    { code: 'db.error("q", { password });' },
    // Not a log-level method on a logger.
    { code: 'logger.child({ token });' },
    // Bare non-secret positional identifier.
    { code: 'logger.info("hello", user);' },
    // `secretary` embeds `secret` only as a substring — whole-token clears it.
    { code: 'logger.info("sec", { secretary });' },
    // Pluralized `tokens` counter is not the singular secret word.
    { code: 'logger.info("usage", { promptTokens, completionTokens });' },
    // console is a logger, but innocuous names still do not fire.
    { code: 'console.log("usage", { tokenCount });' },
    { code: 'console.error("user", { userId });' },
  ],
  invalid: [
    // Object property: shorthand secret names.
    {
      code: 'logger.error("failed", { token });',
      errors: [{ messageId: "noSecretInLog" }],
    },
    {
      code: 'logger.info("auth", { apiKey });',
      errors: [{ messageId: "noSecretInLog" }],
    },
    {
      code: 'logger.warn("login", { password });',
      errors: [{ messageId: "noSecretInLog" }],
    },
    // camelCase whole-token secret.
    {
      code: 'logger.debug("oauth", { clientSecret });',
      errors: [{ messageId: "noSecretInLog" }],
    },
    {
      code: 'logger.info("oauth", { authToken });',
      errors: [{ messageId: "noSecretInLog" }],
    },
    // Explicit key: value form.
    {
      code: 'logger.error("failed", { apiKey: theKey });',
      errors: [{ messageId: "noSecretInLog" }],
    },
    // Bare secret-named positional identifier.
    {
      code: 'logger.info("x", secret);',
      errors: [{ messageId: "noSecretInLog" }],
    },
    // Builder/factory chains still resolve to a logger.
    {
      code: 'logging.getLogger("x").info("auth", { jwt });',
      errors: [{ messageId: "noSecretInLog" }],
    },
    {
      code: 'logger.bind({ id }).error("auth", { credentials });',
      errors: [{ messageId: "noSecretInLog" }],
    },
    {
      code: 'this.logger.error("auth", { signature });',
      errors: [{ messageId: "noSecretInLog" }],
    },
    // console is the JS-idiomatic logger.
    {
      code: 'console.error("failed", { token });',
      errors: [{ messageId: "noSecretInLog" }],
    },
    // Multiple secret properties in one object → one report each.
    {
      code: 'logger.error("failed", { token, apiKey });',
      errors: [
        { messageId: "noSecretInLog" },
        { messageId: "noSecretInLog" },
      ],
    },
  ],
});
