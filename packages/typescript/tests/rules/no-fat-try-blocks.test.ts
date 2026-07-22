import * as tsParser from "@typescript-eslint/parser";
import { RuleTester } from "@typescript-eslint/rule-tester";
import { afterAll, describe, it } from "vitest";

import rule from "../../src/rules/no-fat-try-blocks.js";

RuleTester.afterAll = afterAll;
RuleTester.describe = describe;
RuleTester.it = it;
RuleTester.itOnly = it.only;

const ruleTester = new RuleTester({
  languageOptions: {
    parser: tsParser,
  },
});

ruleTester.run("no-fat-try-blocks", rule, {
  valid: [
    // Exactly three throwing (result-using) statements — at the limit.
    {
      code: `
        function f() {
          try {
            const a = one();
            const b = two();
            const c = three();
          } catch (e) { handle(e); }
        }
      `,
    },
    // Exactly three awaits — at the limit.
    {
      code: `
        async function f() {
          try {
            const a = await one();
            const b = await two();
            const c = await three();
          } catch (e) { handle(e); }
        }
      `,
    },
    // Four statements but only three throw — pure member access is free.
    {
      code: `
        function f() {
          try {
            const a = one();
            const b = a.field;
            const c = two();
            const d = three();
          } catch (e) { handle(e); }
        }
      `,
    },
    // Dominant real-world pattern: ONE awaited action, then trailing
    // fire-and-forget side effects (setters/toast/router/callback). Not fat.
    {
      code: `
        async function f() {
          try {
            await assignTrunk(orgId, trunkId);
            setOpen(false);
            setSelectedOrgId("");
            toast("Success");
            router.refresh();
            onSuccess?.();
          } catch (e) { setError(e); }
        }
      `,
    },
    // Bare fire-and-forget call statements do not count (no await, value used).
    {
      code: `
        function f() {
          try {
            log("a");
            emit("b");
            notify("c");
            track("d");
          } catch (e) { handle(e); }
        }
      `,
    },
    // Pure array / object plumbing does not count, even when assigned.
    {
      code: `
        function f() {
          try {
            const ids = rows.map((r) => r.id);
            const names = rows.filter(Boolean).map((r) => r.name);
            const keys = Object.keys(obj);
            const joined = ids.join(",");
            const has = set.has(x);
          } catch (e) { handle(e); }
        }
      `,
    },
    // `finally` present — exempt regardless of body size.
    {
      code: `
        async function f() {
          try {
            const a = await one();
            const b = await two();
            const c = await three();
            const d = await four();
          } finally { cleanup(); }
        }
      `,
    },
    // Handler re-throws on its last statement — uniform error wrapping, exempt.
    {
      code: `
        async function f() {
          try {
            const a = await one();
            const b = await two();
            const c = await three();
            const d = await four();
          } catch (e) {
            log(e);
            throw new Error("wrapped", { cause: e });
          }
        }
      `,
    },
    // Handler re-throws (bare) — exempt.
    {
      code: `
        async function f() {
          try {
            const a = await one();
            const b = await two();
            const c = await three();
            const d = await four();
          } catch (e) { throw e; }
        }
      `,
    },
    // Throwing calls only in the catch, not the try body.
    {
      code: `
        function f() {
          try {
            const a = one();
          } catch (e) {
            const b = recover(e);
            const c = retry(b);
            const d = report(c);
            const g = finalize(d);
          }
        }
      `,
    },
    // Calls only inside nested function bodies do not count toward the limit.
    {
      code: `
        function f() {
          try {
            const cb1 = () => alpha();
            const cb2 = () => beta();
            const cb3 = () => gamma();
            const cb4 = () => delta();
          } catch (e) { handle(e); }
        }
      `,
    },
    // Compound statements collapse to one each (an if/for/switch counts once).
    {
      code: `
        function f() {
          try {
            if (cond) { const a = a1(); const b = b1(); const c = c1(); }
            for (const x of xs) { const d = d1(x); }
            switch (k) { case 1: { const e = e1(); break; } }
          } catch (e) { handle(e); }
        }
      `,
    },
  ],
  invalid: [
    // Four result-using calls — boundary just over the limit.
    {
      code: `
        function f() {
          try {
            const a = one();
            const b = two();
            const c = three();
            const d = four();
          } catch (e) { handle(e); }
        }
      `,
      errors: [{ messageId: "fatTryBlock" }],
    },
    // Four awaits — multiple independent I/O ops under one swallowing catch.
    {
      code: `
        async function f() {
          try {
            const a = await one();
            const b = await two();
            const c = await three();
            const d = await four();
          } catch (e) { handle(e); }
        }
      `,
      errors: [{ messageId: "fatTryBlock" }],
    },
    // Mixed awaits and result-using sync calls push over the limit.
    {
      code: `
        async function f() {
          try {
            const cfg = parse(raw);
            const res = await fetch(cfg.url);
            const data = await res.json();
            const out = transform(data);
          } catch (e) { handle(e); }
        }
      `,
      errors: [{ messageId: "fatTryBlock" }],
    },
    // `new` (non-pure constructor) whose value is used counts.
    {
      code: `
        function f() {
          try {
            const a = new Widget(x);
            const b = new Gadget(y);
            const c = new Gizmo(z);
            const d = new Doohickey(w);
          } catch (e) { handle(e); }
        }
      `,
      errors: [{ messageId: "fatTryBlock" }],
    },
    // Handler does NOT re-throw (final statement swallows) — fires.
    {
      code: `
        async function f() {
          try {
            const a = await one();
            const b = await two();
            const c = await three();
            const d = await four();
          } catch (e) {
            log(e);
            return null;
          }
        }
      `,
      errors: [{ messageId: "fatTryBlock" }],
    },
    // A conditional throw that is not the last statement does not exempt.
    {
      code: `
        async function f() {
          try {
            const a = await one();
            const b = await two();
            const c = await three();
            const d = await four();
          } catch (e) {
            if (fatal(e)) throw e;
            log(e);
          }
        }
      `,
      errors: [{ messageId: "fatTryBlock" }],
    },
    // Nested-function calls are ignored, but the real throwing statements
    // around them still push the count over the limit.
    {
      code: `
        function f() {
          try {
            const cb = () => nestedCall();
            const a = one();
            const b = two();
            const c = three();
            const d = four();
          } catch (e) { handle(e); }
        }
      `,
      errors: [{ messageId: "fatTryBlock" }],
    },
  ],
});
