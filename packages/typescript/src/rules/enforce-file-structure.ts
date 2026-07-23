import { ESLintUtils, type TSESTree, AST_NODE_TYPES } from "@typescript-eslint/utils";

type MessageIds = "importsFirst" | "useServerDirective";
type Options = readonly [];

// Server-action files: anchored to an `/actions/` path segment, a `*.action.ts`
// filename, or a bare `actions.ts` file. Substrings like `transaction-service`
// or `redaction.ts` deliberately do NOT match.
const SERVER_ACTION_FILE_RE =
  /(?:^|\/)actions\/|\.action\.[jt]sx?$|(?:^|\/)actions\.[jt]sx?$/;

type StatementKind = "import" | "reexport" | "body";

/**
 * Classify a top-level statement by WHAT it introduces, not by the presence of
 * the `export` keyword.
 *
 * - `import ...`                        → "import"
 * - `export ... from`, `export * from`, → "reexport"
 *   `export { a, b }` (local names)
 * - everything else, INCLUDING every    → "body"
 *   exported declaration/function
 *
 * Bucketing exported statements as "body" is the whole point: an exported
 * `interface`/`type`/`enum`/`class`/value-`const` is a declaration and an
 * exported `function` (or `export default <fn>`) is a function — both live in
 * the same body as their non-exported equivalents. That lets the dominant
 * step-down layout (public API first, private helpers below) pass instead of
 * forcing every `export`-prefixed statement into a terminal "exports" section.
 *
 * Re-exports are their own neutral group: a generated `_namespaces` barrel that
 * interleaves `import * as X` / `export { X }` must not be flagged, so
 * re-exports never trigger and are allowed anywhere in the file.
 */
const classifyStatement = (
  statement: TSESTree.ProgramStatement,
): StatementKind => {
  switch (statement.type) {
    case AST_NODE_TYPES.ImportDeclaration:
      return "import";
    case AST_NODE_TYPES.ExportAllDeclaration:
      return "reexport";
    case AST_NODE_TYPES.ExportNamedDeclaration:
      // `export { a } from './x'` / `export { a, b }` re-export names without
      // declaring anything; only `export <decl>` introduces a body statement.
      return statement.declaration === null ? "reexport" : "body";
    default:
      return "body";
  }
};

const isStringDirective = (statement: TSESTree.ProgramStatement): boolean =>
  statement.type === AST_NODE_TYPES.ExpressionStatement &&
  statement.expression.type === AST_NODE_TYPES.Literal &&
  typeof statement.expression.value === "string" &&
  statement.expression.value.startsWith("use ");

const isUseServerDirective = (
  statement: TSESTree.ProgramStatement | undefined,
): boolean => {
  if (statement === undefined) return false;
  if (statement.type !== AST_NODE_TYPES.ExpressionStatement) return false;
  const expr = statement.expression;
  if (expr.type !== AST_NODE_TYPES.Literal) return false;
  return expr.value === "use server";
};

export default ESLintUtils.RuleCreator(
  (name) =>
    `https://github.com/sarj-ai/linting/blob/main/packages/typescript/src/rules/${name}.ts`,
)<Options, MessageIds>({
  name: "enforce-file-structure",
  meta: {
    type: "suggestion",
    docs: {
      description:
        "Require `import` statements to come first, then allow step-down ordering (public API first, private helpers below) for the rest of the file. Exported statements are classified by WHAT they export — an exported interface is a declaration, an exported function is a function — so a public exported function followed by a private helper, or an exported interface among declarations, is allowed. Re-exports (`export { … } from`, `export *`, `export { … }`) are a neutral group, so generated namespace barrels pass. Server-action files (under `/actions/`, named `*.action.ts`, or `actions.ts`) must also begin with a `use server` directive.",
    },
    schema: [],
    messages: {
      importsFirst:
        "File structure violation: import statements must come before other declarations",
      useServerDirective:
        "Server action files must start with 'use server' directive",
    },
  },
  defaultOptions: [],
  create(context) {
    const isServerAction = SERVER_ACTION_FILE_RE.test(context.filename);

    return {
      Program(node: TSESTree.Program): void {
        const body = node.body;

        if (isServerAction && !isUseServerDirective(body[0])) {
          context.report({
            node,
            messageId: "useServerDirective",
          });
        }

        let seenBody = false;

        for (const statement of body) {
          if (isStringDirective(statement)) continue;

          switch (classifyStatement(statement)) {
            case "reexport":
              continue;
            case "body":
              seenBody = true;
              continue;
            case "import":
              if (seenBody) {
                context.report({
                  node: statement,
                  messageId: "importsFirst",
                });
              }
              continue;
          }
        }
      },
    };
  },
});
