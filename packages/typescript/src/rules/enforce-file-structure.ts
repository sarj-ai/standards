import { ESLintUtils, type TSESTree, AST_NODE_TYPES } from "@typescript-eslint/utils";

type MessageIds = "incorrectOrder" | "useServerDirective";
type Options = readonly [];

/**
 * Section ordinals — lower numbers must appear before higher numbers.
 *
 * Per the stepdown rule (see `plugins/sarj-audit/commands/stepdown.md`), only
 * *function* ordering is a violation. Top-level imports, type aliases,
 * interfaces, enums, classes, and value constants are all "declarations" and
 * belong together at the top in any order — so they share a single ordinal and
 * are never flagged relative to one another.
 */
const SECTION = {
  declarations: 0,
  functions: 1,
  exports: 2,
} as const;

const SECTION_NAMES = ["declarations", "functions", "exports"] as const;

type SectionOrdinal = (typeof SECTION)[keyof typeof SECTION];

const sectionName = (ordinal: SectionOrdinal): string => {
  const name = SECTION_NAMES[ordinal];
  // SECTION_NAMES is indexed by SectionOrdinal (0..2) — always defined, but
  // noUncheckedIndexedAccess widens to `string | undefined`, so fall back.
  return name ?? "unknown";
};

// Server-action files: anchored to an `/actions/` path segment, a `*.action.ts`
// filename, or a bare `actions.ts` file. Substrings like `transaction-service`
// or `redaction.ts` deliberately do NOT match.
const SERVER_ACTION_FILE_RE =
  /(?:^|\/)actions\/|\.action\.[jt]sx?$|(?:^|\/)actions\.[jt]sx?$/;

const isFunctionExpression = (node: TSESTree.Expression): boolean =>
  node.type === AST_NODE_TYPES.ArrowFunctionExpression ||
  node.type === AST_NODE_TYPES.FunctionExpression;

/**
 * A `const/let/var` declaration counts as a *function* when every declarator is
 * initialized with a function/arrow expression (`const helper = () => {}`).
 * A value const (`const x = 1`, `const MAX = 5`) is a declaration, not a
 * function — it must not be mis-bucketed.
 */
const isFunctionLikeVariable = (
  statement: TSESTree.VariableDeclaration,
): boolean =>
  statement.declarations.length > 0 &&
  statement.declarations.every(
    (decl) => decl.init !== null && isFunctionExpression(decl.init),
  );

const getStatementSection = (
  statement: TSESTree.ProgramStatement,
): SectionOrdinal => {
  switch (statement.type) {
    case AST_NODE_TYPES.ImportDeclaration:
    case AST_NODE_TYPES.TSTypeAliasDeclaration:
    case AST_NODE_TYPES.TSInterfaceDeclaration:
    case AST_NODE_TYPES.TSEnumDeclaration:
    case AST_NODE_TYPES.ClassDeclaration:
      return SECTION.declarations;
    case AST_NODE_TYPES.VariableDeclaration:
      return isFunctionLikeVariable(statement)
        ? SECTION.functions
        : SECTION.declarations;
    case AST_NODE_TYPES.FunctionDeclaration:
      return SECTION.functions;
    case AST_NODE_TYPES.ExportNamedDeclaration:
    case AST_NODE_TYPES.ExportDefaultDeclaration:
    case AST_NODE_TYPES.ExportAllDeclaration:
      return SECTION.exports;
    default:
      // Executable top-level statements group with functions.
      return SECTION.functions;
  }
};

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
        "Enforce that function definitions follow the file's top-of-file declarations (imports, types, constants, classes) — the stepdown rule. Ordering among non-function declarations is not enforced. Server-action files (under `/actions/`, named `*.action.ts`, or `actions.ts`) must also begin with a `use server` directive.",
    },
    schema: [],
    messages: {
      incorrectOrder:
        "File structure violation: {{current}} should come before {{expected}}",
      useServerDirective:
        "Server action files must start with 'use server' directive",
    },
  },
  defaultOptions: [],
  create(context) {
    const filename = context.filename;
    const isServerAction = SERVER_ACTION_FILE_RE.test(filename);

    return {
      Program(node: TSESTree.Program): void {
        const body = node.body;

        if (isServerAction) {
          const firstNode = body[0];
          if (!isUseServerDirective(firstNode)) {
            context.report({
              node,
              messageId: "useServerDirective",
            });
          }
        }

        let currentSection: SectionOrdinal = SECTION.declarations;

        for (const statement of body) {
          // Skip top-of-file string directives ('use server', 'use client',
          // 'use strict', ...) so they don't get classified as a section.
          if (
            statement.type === AST_NODE_TYPES.ExpressionStatement &&
            statement.expression.type === AST_NODE_TYPES.Literal &&
            typeof statement.expression.value === "string" &&
            statement.expression.value.startsWith("use ")
          ) {
            continue;
          }

          const statementSection = getStatementSection(statement);

          if (statementSection < currentSection) {
            context.report({
              node: statement,
              messageId: "incorrectOrder",
              data: {
                current: sectionName(statementSection),
                expected: sectionName(currentSection),
              },
            });
          } else if (statementSection > currentSection) {
            currentSection = statementSection;
          }
        }
      },
    };
  },
});
