import * as tsParser from "@typescript-eslint/parser";
import { RuleTester } from "@typescript-eslint/rule-tester";
import { afterAll, describe, it } from "vitest";

import rule from "../../src/rules/no-host-interpolated-fetch.js";

RuleTester.afterAll = afterAll;
RuleTester.describe = describe;
RuleTester.it = it;
RuleTester.itOnly = it.only;

const ruleTester = new RuleTester({
  languageOptions: {
    parser: tsParser,
  },
});

ruleTester.run("no-host-interpolated-fetch", rule, {
  valid: [
    // Plain string URLs — nothing dynamic.
    { code: 'fetch("https://api.example.com/items");' },
    { code: 'axios.get("https://api.example.com/items");' },
    // Template with no interpolation at all.
    { code: "fetch(`https://api.example.com/items`);" },
    // First interpolation is in the PATH — origin is static.
    { code: "fetch(`https://api.example.com/items/${id}`);" },
    { code: "fetch(`https://example.com/${path}?q=${q}`);" },
    { code: "fetch(`https://example.com:8080/${path}`);" },
    { code: "axios.post(`https://api.example.com/${path}`, body);" },
    // Relative URLs — no origin in the template.
    { code: "fetch(`/api/items/${id}`);" },
    // Trusted-base-URL pattern: template starts with an allowlisted name.
    { code: "fetch(`${baseUrl}/api/items`);" },
    { code: "fetch(`${API_BASE}/items/${id}`);" },
    { code: "fetch(`${origin}/callback`);" },
    { code: "fetch(`${endpoint}/v1/chat`);" },
    { code: "fetch(`${config.apiBase}/items`);" },
    { code: "fetch(`${env.BASE_URL}/items`);" },
    { code: 'fetch(`${process.env["API_URL"]}/items`);' },
    { code: "fetch(`${getBaseUrl()}/items`);" },
    // Suffix-allowlisted config names (serviceUrl ends in "url").
    { code: "fetch(`${serviceUrl}/items`);" },
    { code: "axios.get(`${baseUrl}/items/${id}`);" },
    { code: "axios.request(`${apiEndpoint}/items`);" },
    // env/config/settings member accesses are deployment configuration and
    // are exempt even in the origin position after a literal scheme.
    { code: "fetch(`https://${c.env.POSTHOG_API_HOST}${path}`);" },
    { code: "fetch(`https://${process.env.API_HOST}/items`);" },
    { code: 'fetch(`https://${process.env["POSTHOG_HOST"]}/items`);' },
    { code: "fetch(`https://${config.apiHost}/items`);" },
    { code: "fetch(`https://${settings.host}/callback`);" },
    { code: "axios.get(`https://${c.env.UPSTREAM_HOST}/items`);" },
    // ... and in the leading position too.
    { code: "fetch(`${c.env.POSTHOG_API_HOST}${path}`);" },
    // Symmetric name allowlist: a PLAIN identifier named like a base-URL/host
    // constant is exempt in the origin position after a literal scheme —
    // mirrors the posthog.ts pattern (local copied from c.env).
    {
      code: "const apiHost = c.env.POSTHOG_API_HOST; fetch(`https://${apiHost}${path}`);",
    },
    { code: "fetch(`https://${apiHost}/x`);" },
    { code: "fetch(`https://${serviceUrl}/items`);" },
    { code: "axios.get(`https://${upstreamEndpoint}/items`);" },
    // KNOWN GAP (documented false-negative): the name exemption has no data
    // flow — a maliciously-fed local with a trusted-looking name escapes in
    // the origin position too, same trade-off as the leading-position
    // heuristic.
    {
      code: "const apiHost = req.query.host; fetch(`https://${apiHost}/callback`);",
    },
    // new URL with a trusted base as second argument — template is a path.
    { code: "fetch(new URL(`/items/${id}`, baseUrl));" },
    // Non-request calls are out of scope.
    { code: "logger.info(`https://${host}/x`);" },
    { code: "const u = `https://${host}/x`;" },
    // axios methods outside the checked set are out of scope.
    { code: "axios.head(`https://${host}/x`);" },
    // KNOWN GAP (documented false-negative): name-based exemption only, no
    // data flow — the identifier is named like a base URL/host constant even
    // though it came from user input.
    {
      code: "const host = req.query.host; fetch(`${host}/callback`);",
    },
    // KNOWN GAP (documented false-negative): string concatenation is not a
    // template literal and is not analyzed.
    { code: 'fetch("https://" + host + "/x");' },
    // KNOWN GAP (documented false-negative): template built in a variable
    // before the call — no data flow into the fetch argument.
    { code: "const u = `https://${host}/x`; fetch(u);" },
    // KNOWN GAP (documented false-negative): no visible scheme, ambiguous
    // bare-host head is skipped.
    { code: "fetch(`api.${tld}/items`);" },
    // KNOWN GAP (documented false-negative): axios instances and config
    // objects are not matched.
    { code: "client.get(`https://${host}/x`);" },
    { code: "axios.request({ url: `https://${host}/x` });" },
  ],
  invalid: [
    // Interpolated host directly after the scheme, name not base-URL-like.
    {
      code: "fetch(`https://${userInput}/x`);",
      errors: [{ messageId: "hostInterpolation" }],
    },
    // Interpolated subdomain — attacker-chosen label in the host.
    {
      code: "fetch(`https://${userInput}.example-cdn.com/assets`);",
      errors: [{ messageId: "hostInterpolation" }],
    },
    // User-influenced member expression in the origin position after a
    // literal scheme — the true-positive shape; env/config exemption must NOT
    // extend to plain member expressions.
    {
      code: "fetch(`https://${req.query.host}/callback`);",
      errors: [{ messageId: "hostInterpolation" }],
    },
    {
      code: "fetch(`https://${params.host}/redirect`);",
      errors: [{ messageId: "hostInterpolation" }],
    },
    // KNOWN LIMITATION (false positive, no data flow): an env value copied
    // into a local whose name matches nothing in the allowlist stays flagged.
    {
      code: "const h = c.env.API_HOST; fetch(`https://${h}/items`);",
      errors: [{ messageId: "hostInterpolation" }],
    },
    // Interpolated subdomain label — `slug` is not a base-URL-like name.
    {
      code: "fetch(`https://${slug}.example.com/x`);",
      errors: [{ messageId: "hostInterpolation" }],
    },
    // No path at all — the whole tail is origin.
    {
      code: "fetch(`http://${target}`);",
      errors: [{ messageId: "hostInterpolation" }],
    },
    // Interpolated port is still in the origin.
    {
      code: "fetch(`https://example.com:${port}/x`);",
      errors: [{ messageId: "hostInterpolation" }],
    },
    // Protocol-relative URL.
    {
      code: "fetch(`//${target}/x`);",
      errors: [{ messageId: "hostInterpolation" }],
    },
    // Starts with an interpolation whose name is NOT base-URL-like.
    {
      code: "fetch(`${target}/callback`);",
      errors: [{ messageId: "hostInterpolation" }],
    },
    {
      code: "fetch(`${req.body.target}/callback`);",
      errors: [{ messageId: "hostInterpolation" }],
    },
    // axios methods.
    {
      code: "axios.get(`https://${target}/x`);",
      errors: [{ messageId: "hostInterpolation" }],
    },
    {
      code: "axios.post(`https://${target}/x`, data);",
      errors: [{ messageId: "hostInterpolation" }],
    },
    {
      code: "axios.put(`https://${target}/x`, data);",
      errors: [{ messageId: "hostInterpolation" }],
    },
    {
      code: "axios.patch(`https://${target}/x`, data);",
      errors: [{ messageId: "hostInterpolation" }],
    },
    {
      code: "axios.delete(`https://${sub}.internal.example/x`);",
      errors: [{ messageId: "hostInterpolation" }],
    },
    {
      code: "axios.request(`https://${target}/x`);",
      errors: [{ messageId: "hostInterpolation" }],
    },
    // new URL(...) passed directly to fetch.
    {
      code: "fetch(new URL(`https://${target}/x`));",
      errors: [{ messageId: "hostInterpolation" }],
    },
  ],
});
