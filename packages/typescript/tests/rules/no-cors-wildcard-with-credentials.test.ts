import * as tsParser from "@typescript-eslint/parser";
import { RuleTester } from "@typescript-eslint/rule-tester";
import { afterAll, describe, it } from "vitest";

import rule from "../../src/rules/no-cors-wildcard-with-credentials.js";

RuleTester.afterAll = afterAll;
RuleTester.describe = describe;
RuleTester.it = it;
RuleTester.itOnly = it.only;

const ruleTester = new RuleTester({
  languageOptions: {
    parser: tsParser,
  },
});

ruleTester.run("no-cors-wildcard-with-credentials", rule, {
  valid: [
    // Wildcard origin WITHOUT credentials — safe (browser blocks credentialed
    // wildcard anyway). This is the real demo-gateway CORS shape.
    { code: "app.use(cors({ origin: '*' }));" },
    {
      code: "const CORS = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'POST, GET, OPTIONS' };",
    },
    { code: "res.setHeader('Access-Control-Allow-Origin', '*');" },
    // Credentials WITH a specific origin — safe.
    {
      code: "app.use(cors({ origin: 'https://app.example.com', credentials: true }));",
    },
    {
      code: "app.use(cors({ origin: ['https://a.example.com', 'https://b.example.com'], credentials: true }));",
    },
    {
      code: "const CORS = { 'Access-Control-Allow-Origin': 'https://app.example.com', 'Access-Control-Allow-Credentials': 'true' };",
    },
    // credentials: false with wildcard — safe.
    { code: "app.use(cors({ origin: '*', credentials: false }));" },
    // A `"*"` string unrelated to CORS.
    { code: "const glob = '*';" },
    { code: "const pattern = { match: '*' };" },
    // Only one manual header (origin wildcard) with credentials for a DIFFERENT
    // origin value — the ACAC set is not "true".
    {
      code: "res.setHeader('Access-Control-Allow-Origin', '*'); res.setHeader('Access-Control-Allow-Credentials', 'false');",
    },
    // Wildcard origin and credentials=true set in SEPARATE function scopes —
    // must not pair up across scopes.
    {
      code: "function a() { res.setHeader('Access-Control-Allow-Origin', '*'); } function b() { res.setHeader('Access-Control-Allow-Credentials', 'true'); }",
    },
    // credentials=true header alone.
    { code: "res.setHeader('Access-Control-Allow-Credentials', 'true');" },
    // Non-cors call named something else with a wildcard+credentials-shaped
    // object should still be safe when keys are unrelated.
    { code: "configure({ origin: '*', credentials: true });" },
  ],
  invalid: [
    // cors() bare "*" origin + credentials.
    {
      code: "app.use(cors({ origin: '*', credentials: true }));",
      errors: [{ messageId: "corsWildcardWithCredentials" }],
    },
    // cors() array ["*"] origin + credentials.
    {
      code: "app.use(cors({ origin: ['*'], credentials: true }));",
      errors: [{ messageId: "corsWildcardWithCredentials" }],
    },
    // cors() conditional "*" branch + credentials.
    {
      code: "app.use(cors({ origin: isDev ? allowed : '*', credentials: true }));",
      errors: [{ messageId: "corsWildcardWithCredentials" }],
    },
    // new Cors(...) form.
    {
      code: "const c = new Cors({ origin: '*', credentials: true });",
      errors: [{ messageId: "corsWildcardWithCredentials" }],
    },
    // Two-header object literal.
    {
      code: "const headers = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Credentials': 'true' };",
      errors: [{ messageId: "corsWildcardWithCredentials" }],
    },
    // Case-insensitive header names in object literal.
    {
      code: "const headers = { 'access-control-allow-origin': '*', 'access-control-allow-credentials': 'TRUE' };",
      errors: [{ messageId: "corsWildcardWithCredentials" }],
    },
    // NextResponse header object literal.
    {
      code: "return new NextResponse(body, { headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Credentials': 'true' } });",
      errors: [{ messageId: "corsWildcardWithCredentials" }],
    },
    // setHeader pair in the same scope.
    {
      code: "res.setHeader('Access-Control-Allow-Origin', '*'); res.setHeader('Access-Control-Allow-Credentials', 'true');",
      errors: [{ messageId: "corsWildcardWithCredentials" }],
    },
    // headers.set pair in the same function scope.
    {
      code: "function h() { headers.set('Access-Control-Allow-Origin', '*'); headers.set('Access-Control-Allow-Credentials', 'true'); }",
      errors: [{ messageId: "corsWildcardWithCredentials" }],
    },
    // Boolean-coerced credentials value on setHeader.
    {
      code: "res.setHeader('Access-Control-Allow-Origin', '*'); res.setHeader('Access-Control-Allow-Credentials', true);",
      errors: [{ messageId: "corsWildcardWithCredentials" }],
    },
  ],
});
