import * as tsParser from "@typescript-eslint/parser";
import { RuleTester } from "@typescript-eslint/rule-tester";
import { afterAll, describe, it } from "vitest";

import rule from "../../src/rules/no-insecure-random-id.js";

RuleTester.afterAll = afterAll;
RuleTester.describe = describe;
RuleTester.it = it;
RuleTester.itOnly = it.only;

const ruleTester = new RuleTester({
  languageOptions: {
    parser: tsParser,
  },
});

ruleTester.run("no-insecure-random-id", rule, {
  valid: [
    // Bare `Math.random()` for jitter — not an identifier.
    { code: "const jitter = Math.random() * 100;" },
    // Sampling / probability roll.
    { code: "if (Math.random() < 0.5) doThing();" },
    { code: "const sample = Math.random();" },
    { code: "const roll = Math.floor(Math.random() * 6) + 1;" },
    // A `.toString(36)` on something that is NOT Math.random() is fine.
    { code: "const hex = (255).toString(16);" },
    { code: "const label = value.toString(36);" },
    // `.toString` with a non-36 radix on Math.random() is not the flagged idiom
    // and the binding name is non-sensitive.
    { code: "const ratio = Math.random().toString();" },
    { code: "const ratio = Math.random().toString(10);" },
    // The prescribed secure replacements.
    { code: "const id = crypto.randomUUID();" },
    { code: "const sessionToken = crypto.randomUUID();" },
    {
      code: "const key = crypto.getRandomValues(new Uint8Array(16));",
    },
    // Sensitive-sounding name but no Math.random() involved.
    { code: "const token = generateToken();" },
    // Math.random() whose enclosing name is not sensitive.
    { code: "const opacity = Math.random();" },
    { code: "const delayMs = Math.random() * 1000;" },
    // Math.random() in a property with a non-sensitive name.
    { code: "const cfg = { jitter: Math.random() };" },
  ],
  invalid: [
    // Trigger 1: classic `.toString(36)` insecure id idiom.
    {
      code: "const x = Math.random().toString(36).slice(2);",
      errors: [{ messageId: "insecureRandomId" }],
    },
    {
      code: "const x = Math.random().toString(36);",
      errors: [{ messageId: "insecureRandomId" }],
    },
    {
      code: "const x = Math.random().toString(36).substring(2, 15);",
      errors: [{ messageId: "insecureRandomId" }],
    },
    // toString(36) idiom even when the binding name is innocuous.
    {
      code: "const value = Math.random().toString(36).slice(2);",
      errors: [{ messageId: "insecureRandomId" }],
    },
    // Trigger 2: name-based — variable declarators.
    {
      code: "const sessionToken = Math.random();",
      errors: [{ messageId: "insecureRandomId" }],
    },
    {
      code: "const id = Math.random();",
      errors: [{ messageId: "insecureRandomId" }],
    },
    {
      code: "const apiKey = Math.random();",
      errors: [{ messageId: "insecureRandomId" }],
    },
    {
      code: "const userSecret = Math.random();",
      errors: [{ messageId: "insecureRandomId" }],
    },
    {
      code: "const uuid = Math.random();",
      errors: [{ messageId: "insecureRandomId" }],
    },
    {
      code: "const nonce = Math.random();",
      errors: [{ messageId: "insecureRandomId" }],
    },
    {
      code: "const password = Math.random();",
      errors: [{ messageId: "insecureRandomId" }],
    },
    {
      code: "const salt = Math.random();",
      errors: [{ messageId: "insecureRandomId" }],
    },
    // Name-based even with surrounding arithmetic.
    {
      code: "const token = `t-${Math.random()}`;",
      errors: [{ messageId: "insecureRandomId" }],
    },
    // Trigger 2: object property key.
    {
      code: "const obj = { sessionId: Math.random() };",
      errors: [{ messageId: "insecureRandomId" }],
    },
    {
      code: "const obj = { 'access-token': Math.random() };",
      errors: [{ messageId: "insecureRandomId" }],
    },
    // Trigger 2: class property definition.
    {
      code: "class S { token = Math.random(); }",
      errors: [{ messageId: "insecureRandomId" }],
    },
  ],
});
