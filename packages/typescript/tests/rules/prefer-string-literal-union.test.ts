import * as tsParser from "@typescript-eslint/parser";
import { RuleTester } from "@typescript-eslint/rule-tester";
import { afterAll, describe, it } from "vitest";

import rule from "../../src/rules/prefer-string-literal-union.js";

RuleTester.afterAll = afterAll;
RuleTester.describe = describe;
RuleTester.it = it;
RuleTester.itOnly = it.only;

const ruleTester = new RuleTester({
  languageOptions: {
    parser: tsParser,
  },
});

ruleTester.run("prefer-string-literal-union", rule, {
  valid: [
    // Already the prescribed pattern — a string-literal union.
    { code: 'type Status = "active" | "inactive";' },
    { code: 'interface Foo { status: "active" | "inactive"; }' },
    // Lone `status: string` with no corroboration — an open-set API DTO field.
    { code: "interface ApiUser { id: string; status: string; name: string; }" },
    { code: "class Dto { status: string = ''; }" },
    // DB-row cast whose `status` is also compared in a cluster elsewhere in the
    // file: the field must NOT be corroborated by the file-wide cluster (only
    // the cluster diagnostic fires, at the comparison — asserted in `invalid`).
    {
      code: "type Row = { status: string }; function ok(r: Row) { return true; }",
    },
    // Non-choice names never fire, even alongside a union sibling.
    {
      code: 'interface Foo { name: string; kind: "a" | "b"; }',
    },
    // A single-literal comparison is not a cluster.
    {
      code: "function f(x: string) { return x === 'active'; }",
    },
    // Comparison against a single literal in a switch is not a cluster.
    {
      code: "function f(x: string) { switch (x) { case 'active': return 1; } }",
    },
    // Generated files opt out even with obvious violations.
    {
      code: "interface Foo { status: string; kind: 'a' | 'b'; } function g(x: string){ return x === 'a' || x === 'b'; }",
      filename: "/repo/src/api.gen.ts",
    },
    {
      code: "interface Foo { status: string; kind: 'a' | 'b'; }",
      filename: "/repo/src/generated/api.ts",
    },
    {
      code: "// @generated\ninterface Foo { status: string; kind: 'a' | 'b'; }",
    },
    {
      code: "interface Foo { status: string; kind: 'a' | 'b'; }",
      filename: "/repo/src/api.d.ts",
    },
    // Uppercase / long literals are not enum-shaped tokens.
    {
      code: "function f(x: string) { return x === 'Active Status Here' || x === 'Another Long Value'; }",
    },
  ],
  invalid: [
    // Choice field corroborated by a sibling string-literal union.
    {
      code: 'interface Order { status: string; kind: "a" | "b"; }',
      errors: [{ messageId: "bareChoiceField", data: { name: "status" } }],
    },
    // A comparison cluster fires the cluster diagnostic (but a bare field is
    // NOT corroborated by a file-wide cluster — that would flag DTO fields).
    {
      code: "interface Order { callStatus: string; } function h(o: Order) { return o.callStatus === 'open' || o.callStatus === 'closed'; }",
      errors: [{ messageId: "comparisonCluster" }],
    },
    // Class field corroborated by sibling union.
    {
      code: 'class Job { state: string; priority: "low" | "high" = "low"; }',
      errors: [{ messageId: "bareChoiceField", data: { name: "state" } }],
    },
    // Pure comparison cluster: 2 distinct literals via `===`.
    {
      code: "function route(mode: string) { if (mode === 'read') return 1; if (mode === 'write') return 2; return 0; }",
      errors: [{ messageId: "comparisonCluster", data: { key: "mode" } }],
    },
    // Cluster via `switch` with 2+ string cases.
    {
      code: "function pick(role: string) { switch (role) { case 'admin': return 1; case 'user': return 2; default: return 0; } }",
      errors: [{ messageId: "comparisonCluster", data: { key: "role" } }],
    },
    // Member-expression cluster. The inline `tier: string` param has no sibling
    // union, so only the cluster fires — the bare field is not corroborated.
    {
      code: "function f(o: { tier: string }) { return o.tier === 'gold' || o.tier === 'silver'; }",
      errors: [{ messageId: "comparisonCluster", data: { key: "o.tier" } }],
    },
    // Bare member-expression cluster with no field declaration.
    {
      code: "function g(u: Account) { return u.plan.tier === 'gold' || u.plan.tier === 'silver'; }",
      errors: [{ messageId: "comparisonCluster", data: { key: "u.plan.tier" } }],
    },
  ],
});
