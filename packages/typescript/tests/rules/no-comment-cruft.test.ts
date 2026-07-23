import { RuleTester } from "@typescript-eslint/rule-tester";
import { afterAll, describe, it } from "vitest";

import rule from "../../src/rules/no-comment-cruft.js";

RuleTester.afterAll = afterAll;
RuleTester.describe = describe;
RuleTester.it = it;
RuleTester.itOnly = it.only;

const ruleTester = new RuleTester();

ruleTester.run("no-comment-cruft", rule, {
  valid: [
    // Prose "why" comment is the legitimate use.
    { code: "// retry because the upstream API is flaky\nconst x = retry();" },
    // Trailing explanatory comment.
    { code: "const x = compute(); // cached when warm" },
    // JSDoc / @fileoverview headers are never flagged.
    {
      code: "/**\n * @fileoverview does a thing\n * with detail\n * across lines\n * and more\n */\nexport const x = 1;",
    },
    // Directive comments are ignored (TODO/FIXME carry an owner elsewhere).
    { code: "// TODO@nmaswood: return cachedValue();\nconst x = 1;" },
    { code: "// prettier-ignore\nconst x = 1;" },
    // A short leading comment block (< 4 lines) is fine.
    { code: "// the entrypoint\nimport x from 'y';" },
    // Prose with `key=value` / comparisons is not commented-out code.
    { code: "// 0=Monday … 6=Sunday — matches Python's WeekDay IntEnum\nexport const days = 1;" },
    { code: "// if x === y the cache is warm\nconst x = 1;" },
    { code: "// returns true => proceed\nconst ok = true;" },
    // Prose `word = phrase` with no code-tail is not commented-out code.
    { code: "// count = number of items in the cart\nconst total = 1;" },
    { code: "// delta = new value minus old value\nconst d = 1;" },
    // License header preamble is exempt.
    {
      code: "// Copyright 2023 Acme, Inc.\n// Licensed under the Apache License 2.0.\n// You may not use this file except in compliance.\n// See the License for details.\nimport x from 'y';",
    },
    // Block-comment MIT license banner (dashed rule) is exempt.
    {
      code: "/*---------------------------------------------------------------------------------------------\n *  Copyright (c) Microsoft Corporation. All rights reserved.\n *  Licensed under the MIT License. See License.txt in the project root for license information.\n *--------------------------------------------------------------------------------------------*/\nimport x from 'y';",
    },
    // Code-shaped line under a prose lead-in is an illustration, not dead code.
    {
      code: "// For example:\n// var o = {…};\nconst x = 1;",
    },
    // Pseudo-code placeholder line is not commented-out code.
    {
      code: "const x = 1;\n// obj.value = %sent%;\nconst y = 2;",
    },
    // Triple-slash TS reference directive is a directive, not a preamble.
    {
      code: '/// <reference types="node" />\nimport x from "y";',
    },
  ],
  invalid: [
    {
      code: "const x = 1;\n// return x + 1;\nconst y = 2;",
      errors: [{ messageId: "commentedOutCode" }],
    },
    {
      code: "// import { foo } from './bar';\nexport const x = 1;",
      errors: [{ messageId: "commentedOutCode" }],
    },
    // Assignment WITH a code-tail is still commented-out code.
    {
      code: "const x = 1;\n// config.value = getValue();\nconst y = 2;",
      errors: [{ messageId: "commentedOutCode" }],
    },
    {
      code: "const x = 1;\n// =====================\nconst y = 2;",
      errors: [{ messageId: "sectionBanner" }],
    },
    {
      code: "const x = 1;\n// #region helpers\nconst y = 2;",
      errors: [{ messageId: "sectionBanner" }],
    },
    {
      code: "// This module wires the thing.\n// It is old.\n// Be careful.\n// Ask first.\nimport x from 'y';",
      errors: [{ messageId: "fileHeaderPreamble" }],
    },
    // A genuine multi-line commented-out block still fires on every line.
    {
      code: "const x = 1;\n// const a = 1;\n// const b = 2;\nconst y = 2;",
      errors: [
        { messageId: "commentedOutCode" },
        { messageId: "commentedOutCode" },
      ],
    },
    // A real section banner that is NOT a license header still fires.
    {
      code: "const x = 1;\n// ==== SECTION ====\nconst y = 2;",
      errors: [{ messageId: "sectionBanner" }],
    },
  ],
});
