/**
 * @fileoverview Flag `'use client'` files with no hooks or event handlers.
 *
 * If a file is marked `'use client'` but contains no hook calls
 * (`useState`/`useEffect`/etc.), no JSX event handlers (`onClick`,
 * `onChange`, etc.), no browser globals, no client-only imports, and no
 * other client-side indicators (classes, re-exports), the directive is
 * likely unnecessary and the file could be a React Server Component —
 * improving cold-start, bundle size, and SEO.
 *
 * False-positive watch: components that only use client-side context
 * (e.g. theme providers) without hooks or events still need `'use client'`.
 *
 * References:
 *   - https://nextjs.org/docs/app/building-your-application/rendering/client-components
 */

import {
  AST_NODE_TYPES,
  ESLintUtils,
  type TSESTree,
} from "@typescript-eslint/utils";
import type { RuleContext, Scope } from "@typescript-eslint/utils/ts-eslint";

type MessageIds = "unnecessaryUseClient";
type Options = readonly [];

const HOOK_REGEX = /^use([A-Z]|$)/;
const EVENT_PROP_REGEX = /^on[A-Z]/;
const ERROR_FILE_REGEX = /\b(?:global-)?error\.[jt]sx?$/;

const BROWSER_GLOBALS: ReadonlySet<string> = new Set([
  "window",
  "document",
  "navigator",
  "localStorage",
  "sessionStorage",
  "location",
  "history",
  "screen",
  "requestAnimationFrame",
  "cancelAnimationFrame",
  "CustomEvent",
  "Event",
  "MouseEvent",
  "KeyboardEvent",
  "TouchEvent",
]);

const CLIENT_ONLY_PACKAGES_REGEX =
  /^(?:@radix-ui\/|framer-motion|react-dom|react-day-picker|@floating-ui\/|react-select|react-toastify|react-hook-form|recharts|react-dropzone|react-slick|react-swipeable|react-resizable|react-draggable|react-beautiful-dnd|@hello-pangea\/dnd|react-virtualized|react-window|@tanstack\/react-table|@tanstack\/react-query|react-redux|recoil|jotai|zustand|@tippyjs\/react|react-color|react-datepicker|next-themes|react-helmet|react-helmet-async|styled-components|@emotion\/)/;

type Ctx = Readonly<RuleContext<MessageIds, Options>>;

const isUseClientDirective = (
  node: TSESTree.Statement,
): node is TSESTree.ExpressionStatement => {
  return (
    node.type === AST_NODE_TYPES.ExpressionStatement &&
    node.expression.type === AST_NODE_TYPES.Literal &&
    node.expression.value === "use client"
  );
};

const isGlobalReference = (
  node: TSESTree.Identifier,
  context: Ctx,
): boolean => {
  if (!BROWSER_GLOBALS.has(node.name)) return false;

  const parent = node.parent;
  if (parent !== undefined) {
    // `obj.window` — `window` is a property name, not a global reference.
    if (
      parent.type === AST_NODE_TYPES.MemberExpression &&
      parent.property === node &&
      !parent.computed
    ) {
      return false;
    }
    // `{ window: ... }` — property key, not a global reference.
    if (
      parent.type === AST_NODE_TYPES.Property &&
      parent.key === node &&
      !parent.computed
    ) {
      return false;
    }
    // Type annotations / type-only positions are not runtime references.
    if (parent.type.startsWith("TS")) {
      return false;
    }
  }

  // If there's a local binding for this name anywhere up the chain, it's not
  // a reference to the browser global.
  let scope: Scope.Scope | null = context.sourceCode.getScope(node);
  while (scope !== null) {
    const variable = scope.set.get(node.name);
    if (variable !== undefined && variable.defs.length > 0) {
      return false;
    }
    scope = scope.upper;
  }

  return true;
};

export default ESLintUtils.RuleCreator(
  (name) =>
    `https://github.com/sarj-ai/linting/blob/main/packages/typescript/src/rules/${name}.ts`,
)<Options, MessageIds>({
  name: "no-unnecessary-use-client",
  meta: {
    type: "suggestion",
    docs: {
      description:
        "Flag `'use client'` files with no hooks or event handlers — they could be RSC.",
    },
    schema: [],
    messages: {
      unnecessaryUseClient:
        "'use client' directive but no hooks (use*), JSX event handlers (on*), browser globals, or client-only imports found. Consider removing the directive and serving as a React Server Component.",
    },
  },
  defaultOptions: [],
  create(context) {
    const filename = context.filename;
    if (ERROR_FILE_REGEX.test(filename)) {
      return {};
    }

    let directiveNode: TSESTree.ExpressionStatement | null = null;
    let hasClientIndicator = false;

    const markIfHookOrContext = (
      callee: TSESTree.CallExpression["callee"],
    ): void => {
      if (callee.type === AST_NODE_TYPES.Identifier) {
        if (HOOK_REGEX.test(callee.name) || callee.name === "createContext") {
          hasClientIndicator = true;
        }
        return;
      }
      if (
        callee.type === AST_NODE_TYPES.MemberExpression &&
        callee.property.type === AST_NODE_TYPES.Identifier
      ) {
        const name = callee.property.name;
        if (HOOK_REGEX.test(name) || name === "createContext") {
          hasClientIndicator = true;
        }
      }
    };

    return {
      Program(node): void {
        for (const stmt of node.body) {
          // Directives must be the first statements; once we see a non-
          // ExpressionStatement, stop scanning.
          if (stmt.type !== AST_NODE_TYPES.ExpressionStatement) break;
          if (isUseClientDirective(stmt)) {
            directiveNode = stmt;
            break;
          }
        }
      },
      CallExpression(node): void {
        // The `Program` visitor (entered first) has already determined whether
        // this file has a `'use client'` directive. If it doesn't, the result
        // can't change — skip all of the per-node indicator work, including the
        // hot scope-resolution in the `Identifier` visitor below.
        if (directiveNode === null) return;
        markIfHookOrContext(node.callee);
      },
      JSXAttribute(node): void {
        if (directiveNode === null) return;
        if (
          node.name.type === AST_NODE_TYPES.JSXIdentifier &&
          EVENT_PROP_REGEX.test(node.name.name)
        ) {
          hasClientIndicator = true;
        }
      },
      ImportDeclaration(node): void {
        if (directiveNode === null) return;
        if (
          typeof node.source.value === "string" &&
          CLIENT_ONLY_PACKAGES_REGEX.test(node.source.value)
        ) {
          hasClientIndicator = true;
        }
      },
      ExportNamedDeclaration(node): void {
        if (directiveNode === null) return;
        if (node.source !== null) {
          hasClientIndicator = true;
        }
      },
      ExportAllDeclaration(node): void {
        if (directiveNode === null) return;
        if (node.source !== null) {
          hasClientIndicator = true;
        }
      },
      ClassDeclaration(): void {
        if (directiveNode === null) return;
        hasClientIndicator = true;
      },
      ClassExpression(): void {
        if (directiveNode === null) return;
        hasClientIndicator = true;
      },
      Identifier(node): void {
        if (directiveNode === null) return;
        if (isGlobalReference(node, context)) {
          hasClientIndicator = true;
        }
      },
      "Program:exit"(): void {
        if (directiveNode !== null && !hasClientIndicator) {
          context.report({
            node: directiveNode,
            messageId: "unnecessaryUseClient",
          });
        }
      },
    };
  },
});
