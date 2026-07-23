/**
 * @fileoverview Disallow silently swallowing an error in a `catch` clause by
 * returning a "sentinel" empty value as the final/only statement.
 *
 * A `catch` block whose last statement is `return null` / `return undefined` /
 * `return false` / `return []` / `return {}` (and which never `throw`s) discards
 * the caught error entirely. Downstream callers can't distinguish a genuine
 * empty result from a failure, which is a frequent source of silent data loss
 * and broken idempotency decisions.
 *
 * This rule is deliberately conservative — it prefers false negatives over
 * false positives. It does NOT flag:
 *   - catch blocks that `throw`/rethrow anywhere in their body,
 *   - returns of a computed/meaningful value (calls, identifiers, member
 *     expressions, non-empty literals),
 *   - `return 0` / `return ""`, which are often legitimate results,
 *   - catches that LOG or REPORT the caught error before the sentinel return —
 *     a `console.*`/logger call, or an error-reporting call that takes the
 *     caught binding (`onUnexpectedError(err)`). Here the sentinel is a
 *     deliberate degraded return, not a silent swallow.
 *   - the typed-optional / safe-parse / predicate shape: the try body returns a
 *     parse-style call that throws on bad input (`JSON.parse(x)`, `new RegExp`),
 *     or the enclosing function returns the same sentinel kind on a normal path
 *     (a boolean predicate, a `T | undefined` accessor). Here the sentinel is
 *     the declared contract.
 */

import {
  ESLintUtils,
  type TSESTree,
  AST_NODE_TYPES,
} from "@typescript-eslint/utils";

import {
  isLoggingCall,
  calleeName,
  REPORT_NAME_RE,
} from "./_logging.js";

type MessageIds = "noSentinelReturn";
type Options = readonly [];

type SentinelKind = "nullish" | "boolean" | "array" | "object" | "string";

/** The sentinel "kind" of a returned expression, or null if not a sentinel. */
function sentinelKind(arg: TSESTree.Expression | null): SentinelKind | null {
  if (arg === null) {
    return null;
  }
  if (arg.type === AST_NODE_TYPES.Literal) {
    if (arg.value === null) {
      return "nullish";
    }
    if (typeof arg.value === "boolean") {
      return "boolean";
    }
    if (typeof arg.value === "string") {
      return "string";
    }
    return null;
  }
  if (arg.type === AST_NODE_TYPES.Identifier && arg.name === "undefined") {
    return "nullish";
  }
  if (arg.type === AST_NODE_TYPES.ArrayExpression) {
    return "array";
  }
  if (arg.type === AST_NODE_TYPES.ObjectExpression) {
    return "object";
  }
  return null;
}

/** Whether a returned expression is one of the swallowing sentinels we flag. */
function isSentinelArgument(arg: TSESTree.Expression | null): boolean {
  if (arg === null) {
    return false;
  }
  if (arg.type === AST_NODE_TYPES.Literal && arg.value === null) {
    return true;
  }
  if (arg.type === AST_NODE_TYPES.Literal && arg.value === false) {
    return true;
  }
  if (arg.type === AST_NODE_TYPES.Identifier && arg.name === "undefined") {
    return true;
  }
  if (arg.type === AST_NODE_TYPES.ArrayExpression && arg.elements.length === 0) {
    return true;
  }
  if (
    arg.type === AST_NODE_TYPES.ObjectExpression &&
    arg.properties.length === 0
  ) {
    return true;
  }
  return false;
}

function isFunctionNode(node: TSESTree.Node): boolean {
  return (
    node.type === AST_NODE_TYPES.FunctionDeclaration ||
    node.type === AST_NODE_TYPES.FunctionExpression ||
    node.type === AST_NODE_TYPES.ArrowFunctionExpression
  );
}

function isNode(value: unknown): value is TSESTree.Node {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as { type?: unknown }).type === "string"
  );
}

/**
 * Walk `node`'s subtree applying `visit`, but do not descend into nested
 * function scopes — their statements don't run synchronously for the current
 * catch. Stops early once `visit` returns true.
 */
function walkWithinScope(
  node: TSESTree.Node,
  visit: (current: TSESTree.Node) => boolean,
): boolean {
  let found = false;

  const recurse = (current: TSESTree.Node): void => {
    if (found) {
      return;
    }
    if (visit(current)) {
      found = true;
      return;
    }
    if (isFunctionNode(current)) {
      return;
    }
    for (const key of Object.keys(current)) {
      if (key === "parent") {
        continue;
      }
      const value = (current as unknown as Record<string, unknown>)[key];
      if (Array.isArray(value)) {
        for (const child of value) {
          if (isNode(child)) {
            recurse(child);
          }
        }
      } else if (isNode(value)) {
        recurse(value);
      }
    }
  };

  recurse(node);
  return found;
}

/** Does this subtree throw (ignoring nested function scopes)? */
function containsThrow(node: TSESTree.Node): boolean {
  return walkWithinScope(
    node,
    (current) => current.type === AST_NODE_TYPES.ThrowStatement,
  );
}

/** Are any of a call's arguments exactly the caught-error binding identifier? */
function argsIncludeBinding(
  args: readonly TSESTree.CallExpressionArgument[],
  caughtName: string | null,
): boolean {
  if (caughtName === null) {
    return false;
  }
  return args.some(
    (arg) => arg.type === AST_NODE_TYPES.Identifier && arg.name === caughtName,
  );
}

/**
 * Does the catch body log or report the caught error before the sentinel
 * return? Either a logging call (`console.*` / logger receiver), or an
 * error-reporting call whose name matches `REPORT_NAME_RE` and that takes the
 * caught binding (`onUnexpectedError(err)`).
 */
function logsOrReportsError(
  catchBody: TSESTree.BlockStatement,
  caughtName: string | null,
): boolean {
  return walkWithinScope(catchBody, (current) => {
    if (current.type !== AST_NODE_TYPES.CallExpression) {
      return false;
    }
    if (isLoggingCall(current)) {
      return true;
    }
    const name = calleeName(current.callee);
    return (
      name !== null &&
      REPORT_NAME_RE.test(name) &&
      argsIncludeBinding(current.arguments, caughtName)
    );
  });
}

/** The try block guarded by this catch. */
function tryBlockOf(catchNode: TSESTree.CatchClause): TSESTree.BlockStatement {
  return catchNode.parent.block;
}

/**
 * True when a return argument is a parse-style call that throws on bad input,
 * so returning a sentinel on failure is the declared "safe-parse" contract:
 * `JSON.parse(x)`, `YAML.parse(x)`, `new RegExp(x)`, `new URL(x)`.
 */
function isSafeParseExpression(arg: TSESTree.Expression | null): boolean {
  if (arg === null) {
    return false;
  }
  if (
    arg.type === AST_NODE_TYPES.CallExpression &&
    arg.callee.type === AST_NODE_TYPES.MemberExpression &&
    !arg.callee.computed &&
    arg.callee.property.type === AST_NODE_TYPES.Identifier &&
    arg.callee.property.name === "parse"
  ) {
    return true;
  }
  if (
    arg.type === AST_NODE_TYPES.NewExpression &&
    arg.callee.type === AST_NODE_TYPES.Identifier
  ) {
    return arg.callee.name === "RegExp" || arg.callee.name === "URL";
  }
  return false;
}

/** Does the try body return a safe-parse-style expression? */
function tryReturnsSafeParse(catchNode: TSESTree.CatchClause): boolean {
  return walkWithinScope(
    tryBlockOf(catchNode),
    (current) =>
      current.type === AST_NODE_TYPES.ReturnStatement &&
      isSafeParseExpression(current.argument),
  );
}

/** The nearest enclosing function body, or null. */
function enclosingFunctionBody(
  node: TSESTree.Node,
): TSESTree.BlockStatement | null {
  let current: TSESTree.Node | undefined | null = node.parent;
  while (current !== undefined && current !== null) {
    if (
      isFunctionNode(current) &&
      "body" in current &&
      isNode(current.body) &&
      current.body.type === AST_NODE_TYPES.BlockStatement
    ) {
      return current.body;
    }
    current = current.parent;
  }
  return null;
}

/**
 * True when the enclosing function returns the same sentinel kind on a normal
 * (non-catch) path — a boolean predicate, a `T | undefined` accessor, etc. —
 * so the catch sentinel is the declared contract, not a swallow. Returns inside
 * the flagged catch itself are excluded.
 */
function functionReturnsSameSentinelKindElsewhere(
  catchNode: TSESTree.CatchClause,
  kind: SentinelKind,
): boolean {
  const functionBody = enclosingFunctionBody(catchNode);
  if (functionBody === null) {
    return false;
  }
  return walkWithinScope(functionBody, (current) => {
    if (current.type !== AST_NODE_TYPES.ReturnStatement) {
      return false;
    }
    if (isWithin(current, catchNode.body)) {
      return false;
    }
    return sentinelKind(current.argument) === kind;
  });
}

/** Is `node` inside `ancestor`'s subtree? */
function isWithin(node: TSESTree.Node, ancestor: TSESTree.Node): boolean {
  let current: TSESTree.Node | undefined | null = node;
  while (current !== undefined && current !== null) {
    if (current === ancestor) {
      return true;
    }
    current = current.parent;
  }
  return false;
}

export default ESLintUtils.RuleCreator(
  (name) =>
    `https://github.com/sarj-ai/linting/blob/main/packages/typescript/src/rules/${name}.ts`,
)<Options, MessageIds>({
  name: "no-sentinel-return-on-catch",
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow swallowing a caught error by returning an empty sentinel (`null`, `undefined`, `false`, `[]`, `{}`) as the final statement of a `catch` block, unless the error is logged/reported or the sentinel is the declared safe-parse/predicate contract.",
    },
    schema: [],
    messages: {
      noSentinelReturn:
        "This `catch` block swallows the error by returning an empty sentinel without logging it. Rethrow it, log/report it, or return a typed Result.",
    },
  },
  defaultOptions: [],
  create(context) {
    return {
      CatchClause(node: TSESTree.CatchClause): void {
        const body = node.body.body;
        if (body.length === 0) {
          return;
        }

        const last = body[body.length - 1];
        if (last === undefined || last.type !== AST_NODE_TYPES.ReturnStatement) {
          return;
        }

        if (!isSentinelArgument(last.argument)) {
          return;
        }

        if (containsThrow(node.body)) {
          return;
        }

        const caughtName =
          node.param?.type === AST_NODE_TYPES.Identifier
            ? node.param.name
            : null;

        if (logsOrReportsError(node.body, caughtName)) {
          return;
        }

        if (tryReturnsSafeParse(node)) {
          return;
        }

        const kind = sentinelKind(last.argument);
        if (
          kind !== null &&
          functionReturnsSameSentinelKindElsewhere(node, kind)
        ) {
          return;
        }

        context.report({
          node: last,
          messageId: "noSentinelReturn",
        });
      },
    };
  },
});
