import * as tsParser from "@typescript-eslint/parser";
import { RuleTester } from "@typescript-eslint/rule-tester";
import { afterAll, describe, it } from "vitest";

import rule from "../../src/rules/require-error-cause.js";

RuleTester.afterAll = afterAll;
RuleTester.describe = describe;
RuleTester.it = it;
RuleTester.itOnly = it.only;

const ruleTester = new RuleTester({
  languageOptions: {
    parser: tsParser,
  },
});

ruleTester.run("require-error-cause", rule, {
  valid: [
    // Rethrowing the caught error is fine.
    { code: "try { work(); } catch (err) { throw err; }" },
    // The idiomatic fix: options object with `cause`.
    {
      code: 'try { work(); } catch (err) { throw new Error("failed", { cause: err }); }',
    },
    // Custom error class with cause.
    {
      code: 'try { work(); } catch (err) { throw new SarjError("boom", { cause: err }); }',
    },
    // Caught error passed positionally to a custom error.
    {
      code: "try { work(); } catch (err) { throw new HttpError(500, err); }",
    },
    // Caught error referenced in the message expression.
    {
      code: "try { work(); } catch (err) { throw new Error(`failed: ${err}`); }",
    },
    {
      code: "try { work(); } catch (err) { throw new Error(err.message); }",
    },
    // Shorthand property reference.
    {
      code: 'try { work(); } catch (err) { throw new WrappedError("x", { err }); }',
    },
    // Member-callee custom error with cause.
    {
      code: 'try { work(); } catch (err) { throw new errors.HttpError("x", { cause: err }); }',
    },
    // Computed member access referencing the caught error.
    {
      code: 'try { work(); } catch (err) { throw new Error("x", { cause: map[err] }); }',
    },
    // Throw outside any catch — not in scope for this rule.
    { code: 'function f() { throw new Error("nope"); }' },
    // Throwing something that is not a `new ...Error(...)`.
    { code: "try { work(); } catch (err) { throw wrap(err); }" },
    // Optional catch binding — no identifier to require.
    { code: 'try { work(); } catch { throw new Error("x"); }' },
    // KNOWN GAP (documented false-negative): destructured catch bindings are
    // skipped — there is no single identifier to look for.
    {
      code: 'try { work(); } catch ({ message }) { throw new Error("x"); }',
    },
    // KNOWN GAP (documented false-negative): throws inside nested functions
    // defined in the catch body do not propagate synchronously and are not
    // checked against the outer catch binding.
    {
      code: 'try { work(); } catch (err) { setTimeout(() => { throw new Error("late"); }, 0); }',
    },
    // KNOWN GAP (documented false-negative): error-like classes whose name
    // does not end with "Error" are not recognized.
    {
      code: 'try { work(); } catch (err) { throw new Failure("x"); }',
    },
    // KNOWN GAP (documented false-negative): the reference check is purely
    // syntactic — the shadowed `err` parameter here counts as a reference to
    // the caught error even though it is a different binding.
    {
      code: 'try { work(); } catch (err) { throw new LazyError("x", (err) => format(err)); }',
    },
  ],
  invalid: [
    // Plain new Error with no reference to the caught error.
    {
      code: 'try { work(); } catch (err) { throw new Error("failed"); }',
      errors: [{ messageId: "missingCause" }],
    },
    {
      code: "try { work(); } catch (err) { throw new Error(); }",
      errors: [{ messageId: "missingCause" }],
    },
    // Built-in Error subclasses.
    {
      code: 'try { work(); } catch (e) { throw new TypeError("bad input"); }',
      errors: [{ messageId: "missingCause" }],
    },
    // Custom "-Error" suffixed classes.
    {
      code: 'try { work(); } catch (err) { throw new SarjError("boom"); }',
      errors: [{ messageId: "missingCause" }],
    },
    // Member-expression callee ending in Error.
    {
      code: 'try { work(); } catch (err) { throw new errors.HttpError("x"); }',
      errors: [{ messageId: "missingCause" }],
    },
    // Referencing the caught error elsewhere in the catch does not help —
    // it must appear in the thrown constructor's arguments.
    {
      code: 'try { work(); } catch (err) { console.error(err); throw new Error("failed"); }',
      errors: [{ messageId: "missingCause" }],
    },
    // An options object without the caught error is not enough.
    {
      code: 'try { work(); } catch (err) { throw new Error("failed", { cause: other }); }',
      errors: [{ messageId: "missingCause" }],
    },
    // A non-computed object KEY named like the caught error is a name, not a
    // reference.
    {
      code: 'try { work(); } catch (err) { throw new Error("x", { err: other }); }',
      errors: [{ messageId: "missingCause" }],
    },
    // Ditto for a non-computed member-access property name.
    {
      code: 'try { work(); } catch (err) { throw new Error(ctx.err ? "a" : "b"); }',
      errors: [{ messageId: "missingCause" }],
    },
    // Throw nested in control flow inside the catch body still counts.
    {
      code: 'try { work(); } catch (err) { if (retries > 3) { throw new Error("giving up"); } }',
      errors: [{ messageId: "missingCause" }],
    },
    // Nearest catch wins: the inner catch's binding is the one that must be
    // referenced.
    {
      code: 'try { a(); } catch (outer) { try { b(); } catch (inner) { throw new Error(`x ${outer}`); } }',
      errors: [{ messageId: "missingCause" }],
    },
  ],
});
