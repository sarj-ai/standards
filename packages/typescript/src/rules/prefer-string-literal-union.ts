/**
 * @fileoverview Flag raw `string` used where a closed enumeration is clearly
 * intended, and comparison clusters against a fixed set of string literals.
 * The prescribed replacement is a string-literal union type
 * (`type Status = "active" | "inactive"`) — NOT a `StrEnum`/`enum`, since the
 * companion `no-enum` rule bans TypeScript enums.
 *
 * This is the TypeScript analog of the Python rule SARJ006 (prefer-str-enum).
 * It fires on two shapes:
 *
 * 1. **Choice-like field** — a `TSPropertySignature` (interface / type literal)
 *    or class `PropertyDefinition` whose key's last word is one of the
 *    high-precision CHOICE tokens (`status`, `state`, `kind`, `role`,
 *    `priority`, `severity`, `direction`, `tier`, `stage`, `type`, `mode`,
 *    `level`) and whose type annotation is the bare `string` keyword. Because
 *    open-set API DTO fields (`status: string` from an untyped backend) are the
 *    dominant false positive, a bare field fires ONLY when CORROBORATED by a
 *    sibling string-literal-union member in the SAME interface / class / object
 *    type. A file-wide comparison cluster on the field's name is deliberately
 *    NOT used to corroborate: it flags unrelated same-named fields (DB-row casts
 *    like `as Array<{ status: string }>`, passthrough DTOs). The closed-set fact
 *    is still surfaced — as a `comparisonCluster` diagnostic at the comparison
 *    site, which is the actionable location.
 *
 * 2. **Comparison cluster** — within one function scope, the same identifier or
 *    member expression compared (`===` / `!==` / `==` / `!=`, or a `switch`)
 *    against 2+ distinct short lowercase string literals (each matching
 *    `^[a-z][a-z0-9_-]{0,30}$`). One diagnostic per cluster.
 *
 * `Literal`-union types (`type X = "a" | "b"`) are the target state and never
 * fire. Generated files (`*.gen.ts`, `**\/generated/**`, `*.d.ts`, or a
 * `@generated` marker) opt out.
 */

import {
  ESLintUtils,
  type TSESTree,
  AST_NODE_TYPES,
} from "@typescript-eslint/utils";

type MessageIds = "bareChoiceField" | "comparisonCluster";
type Options = readonly [];

const CHOICE_TOKENS: ReadonlySet<string> = new Set([
  "status",
  "state",
  "kind",
  "role",
  "priority",
  "severity",
  "direction",
  "tier",
  "stage",
  "type",
  "mode",
  "level",
]);

const LOWER_TOKEN_RE = /^[a-z][a-z0-9_-]{0,30}$/;
const MIN_CLUSTER_SIZE = 2;

const BOOLEANISH: ReadonlySet<string> = new Set(["true", "false"]);

/**
 * An enum-shaped token worth a string-literal union: a short lowercase word of
 * 2+ chars that isn't a boolean-string. Single characters (`'a'`), file
 * paths/URLs/i18n keys (contain `/`, `:`, `.`), and `'true'`/`'false'` are NOT
 * closed-enum members — comparing against them is a flag/path/boolean guard.
 */
function isEnumToken(lit: string): boolean {
  return LOWER_TOKEN_RE.test(lit) && lit.length >= 2 && !BOOLEANISH.has(lit);
}

const IGNORE_PATTERNS: readonly RegExp[] = [
  /[\\/]generated[\\/]/,
  /\.gen\.tsx?$/,
  /\.generated\.tsx?$/,
  /\.d\.ts$/,
];

function isIgnoredFile(filename: string, sourceText: string): boolean {
  if (IGNORE_PATTERNS.some((re) => re.test(filename))) {
    return true;
  }
  return /@generated\b/.test(sourceText.slice(0, 1024));
}

/**
 * The trailing word of a camelCase / snake_case identifier, lowercased.
 * `callStatus` -> `status`, `user_role` -> `role`, `estate` -> `estate`.
 */
function lastWord(name: string): string {
  const words = name
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .split(/[_\s]+/)
    .filter((w) => w.length > 0);
  const last = words[words.length - 1] ?? name;
  return last.toLowerCase();
}

function isChoiceLikeName(name: string): boolean {
  return CHOICE_TOKENS.has(lastWord(name));
}

function keyName(
  key: TSESTree.PropertyDefinition["key"] | TSESTree.PropertyName,
): string | null {
  if (key.type === AST_NODE_TYPES.Identifier) {
    return key.name;
  }
  if (key.type === AST_NODE_TYPES.Literal && typeof key.value === "string") {
    return key.value;
  }
  return null;
}

function isStringLiteralMember(t: TSESTree.TypeNode): boolean {
  return (
    t.type === AST_NODE_TYPES.TSLiteralType &&
    t.literal.type === AST_NODE_TYPES.Literal &&
    typeof t.literal.value === "string"
  );
}

/** Whether a type node is a union of 2+ string-literal types. */
function isStringLiteralUnion(node: TSESTree.TypeNode | undefined): boolean {
  if (node?.type !== AST_NODE_TYPES.TSUnionType) {
    return false;
  }
  return node.types.filter(isStringLiteralMember).length >= MIN_CLUSTER_SIZE;
}

/**
 * A union annotation that already expresses a closed set — it contains at least
 * one string-literal member, even mixed with a named type reference
 * (`AgentState | "connecting"`). Used to suppress comparison clusters on refs
 * the author has already given a union type; looser than
 * {@link isStringLiteralUnion}, which gates the DTO-sibling corroboration.
 */
function isLikelyClosedUnion(node: TSESTree.TypeNode | undefined): boolean {
  return (
    node?.type === AST_NODE_TYPES.TSUnionType &&
    node.types.some(isStringLiteralMember)
  );
}

type FunctionLike =
  | TSESTree.FunctionDeclaration
  | TSESTree.FunctionExpression
  | TSESTree.ArrowFunctionExpression;

/**
 * Property names in a type node that are themselves string-literal unions,
 * descending through inline object-type literals and their `&` / `|`
 * combinations (e.g. `Props & { side: "a" | "b" }` -> `{ side }`). Type
 * references to named types (`Props`) can't be resolved without type info and
 * are skipped.
 */
function unionMemberNames(
  typeNode: TSESTree.TypeNode | undefined,
  out: Set<string>,
): void {
  if (typeNode === undefined) {
    return;
  }
  if (
    typeNode.type === AST_NODE_TYPES.TSIntersectionType ||
    typeNode.type === AST_NODE_TYPES.TSUnionType
  ) {
    for (const t of typeNode.types) {
      unionMemberNames(t, out);
    }
    return;
  }
  if (typeNode.type !== AST_NODE_TYPES.TSTypeLiteral) {
    return;
  }
  for (const member of typeNode.members) {
    if (
      member.type === AST_NODE_TYPES.TSPropertySignature &&
      isLikelyClosedUnion(member.typeAnnotation?.typeAnnotation)
    ) {
      const propName = keyName(member.key);
      if (propName !== null) {
        out.add(propName);
      }
    }
  }
}

function bindingName(node: TSESTree.Node): string | null {
  const id = node.type === AST_NODE_TYPES.AssignmentPattern ? node.left : node;
  return id.type === AST_NODE_TYPES.Identifier ? id.name : null;
}

/**
 * Ref keys already declared with a string-literal union type — a comparison
 * cluster on such a ref is the target state, not a violation. Covers an
 * identifier param typed as a union (`m: "a" | "b"` -> `m`), an object-type
 * param property typed as a union (`o: { tier: "a" | "b" }` -> `o.tier`), and a
 * destructured prop typed as a union (`{ side }: Props & { side: "a" | "b" }`
 * -> `side`).
 */
function addUnionRefsFromBinding(
  param: TSESTree.Parameter,
  out: Set<string>,
): void {
  const binding =
    param.type === AST_NODE_TYPES.AssignmentPattern ? param.left : param;

  if (binding.type === AST_NODE_TYPES.ObjectPattern) {
    const members = new Set<string>();
    unionMemberNames(binding.typeAnnotation?.typeAnnotation, members);
    if (members.size === 0) {
      return;
    }
    for (const prop of binding.properties) {
      if (prop.type !== AST_NODE_TYPES.Property) {
        continue;
      }
      const propKey = keyName(prop.key);
      const local = bindingName(prop.value);
      if (propKey !== null && local !== null && members.has(propKey)) {
        out.add(local);
      }
    }
    return;
  }

  if (binding.type !== AST_NODE_TYPES.Identifier) {
    return;
  }
  const typeNode = binding.typeAnnotation?.typeAnnotation;
  if (isLikelyClosedUnion(typeNode)) {
    out.add(binding.name);
    return;
  }
  if (typeNode?.type === AST_NODE_TYPES.TSTypeLiteral) {
    for (const member of typeNode.members) {
      if (
        member.type === AST_NODE_TYPES.TSPropertySignature &&
        isLikelyClosedUnion(member.typeAnnotation?.typeAnnotation)
      ) {
        const propName = keyName(member.key);
        if (propName !== null) {
          out.add(`${binding.name}.${propName}`);
        }
      }
    }
  }
}

function unionRefsFromParams(fn: FunctionLike): Set<string> {
  const out = new Set<string>();
  for (const param of fn.params) {
    addUnionRefsFromBinding(param, out);
  }
  return out;
}

/** A stable key for a plain identifier or non-computed member chain, else null. */
function refKey(node: TSESTree.Node): string | null {
  if (node.type === AST_NODE_TYPES.Identifier) {
    return node.name;
  }
  if (node.type === AST_NODE_TYPES.MemberExpression && !node.computed) {
    const inner = refKey(node.object);
    if (inner === null || node.property.type !== AST_NODE_TYPES.Identifier) {
      return null;
    }
    return `${inner}.${node.property.name}`;
  }
  return null;
}

function strLiteral(node: TSESTree.Node): string | null {
  if (node.type === AST_NODE_TYPES.Literal && typeof node.value === "string") {
    return node.value;
  }
  return null;
}

interface ClusterEntry {
  node: TSESTree.Node;
  literals: Set<string>;
  allTokens: boolean;
}

interface Scope {
  clusters: Map<string, ClusterEntry>;
  unionRefs: Set<string>;
}

interface CollectedProperty {
  name: string;
  container: TSESTree.Node;
  node: TSESTree.Node;
}

export default ESLintUtils.RuleCreator(
  (name) =>
    `https://github.com/sarj-ai/linting/blob/main/packages/typescript/src/rules/${name}.ts`,
)<Options, MessageIds>({
  name: "prefer-string-literal-union",
  meta: {
    type: "suggestion",
    docs: {
      description:
        "Flag raw `string` choice fields and string-literal comparison clusters; prefer a string-literal union type.",
    },
    schema: [],
    messages: {
      bareChoiceField:
        '`{{name}}: string` looks like a choice field — prefer a string-literal union type (e.g. `type X = "a" | "b"`). Enums are banned by `no-enum`; use a union.',
      comparisonCluster:
        '`{{key}}` is compared against a closed set of string literals — define a string-literal union type (e.g. `type X = "a" | "b"`).',
    },
  },
  defaultOptions: [],
  create(context) {
    const filename = context.filename;
    const sourceText = context.sourceCode.getText();
    if (isIgnoredFile(filename, sourceText)) {
      return {};
    }

    const scopeStack: Scope[] = [];
    const validClusters: TSESTree.Node[] = [];
    const bareChoiceProps: CollectedProperty[] = [];
    const containersWithUnion = new Set<TSESTree.Node>();

    function pushScope(fn: FunctionLike): void {
      scopeStack.push({
        clusters: new Map(),
        unionRefs: unionRefsFromParams(fn),
      });
    }

    function isUnionTypedRef(key: string, current: Set<string>): boolean {
      if (current.has(key)) {
        return true;
      }
      return scopeStack.some((s) => s.unionRefs.has(key));
    }

    function popScope(): void {
      const scope = scopeStack.pop();
      if (scope === undefined) {
        return;
      }
      for (const [key, entry] of scope.clusters) {
        if (
          entry.allTokens &&
          entry.literals.size >= MIN_CLUSTER_SIZE &&
          !isUnionTypedRef(key, scope.unionRefs)
        ) {
          validClusters.push(entry.node);
        }
      }
    }

    function accumulate(
      key: string,
      literals: string[],
      node: TSESTree.Node,
    ): void {
      const scope = scopeStack[scopeStack.length - 1];
      if (scope === undefined) {
        return;
      }
      const allTokens = literals.every((lit) => isEnumToken(lit));
      const existing = scope.clusters.get(key);
      if (existing === undefined) {
        scope.clusters.set(key, {
          node,
          literals: new Set(literals),
          allTokens,
        });
        return;
      }
      for (const lit of literals) {
        existing.literals.add(lit);
      }
      existing.allTokens = existing.allTokens && allTokens;
    }

    function collectProperty(
      key: TSESTree.PropertyDefinition["key"] | TSESTree.PropertyName,
      typeNode: TSESTree.TypeNode | undefined,
      container: TSESTree.Node,
      node: TSESTree.Node,
    ): void {
      if (isStringLiteralUnion(typeNode)) {
        containersWithUnion.add(container);
        return;
      }
      if (typeNode?.type !== AST_NODE_TYPES.TSStringKeyword) {
        return;
      }
      const name = keyName(key);
      if (name === null || !isChoiceLikeName(name)) {
        return;
      }
      bareChoiceProps.push({ name, container, node });
    }

    return {
      FunctionDeclaration: pushScope,
      "FunctionDeclaration:exit": popScope,
      FunctionExpression: pushScope,
      "FunctionExpression:exit": popScope,
      ArrowFunctionExpression: pushScope,
      "ArrowFunctionExpression:exit": popScope,

      VariableDeclarator(node: TSESTree.VariableDeclarator): void {
        const scope = scopeStack[scopeStack.length - 1];
        if (
          scope === undefined ||
          node.id.type !== AST_NODE_TYPES.Identifier
        ) {
          return;
        }
        if (isLikelyClosedUnion(node.id.typeAnnotation?.typeAnnotation)) {
          scope.unionRefs.add(node.id.name);
        }
      },

      BinaryExpression(node: TSESTree.BinaryExpression): void {
        if (
          node.operator !== "===" &&
          node.operator !== "!==" &&
          node.operator !== "==" &&
          node.operator !== "!="
        ) {
          return;
        }
        const leftKey = refKey(node.left);
        const rightLit = strLiteral(node.right);
        const rightKey = refKey(node.right);
        const leftLit = strLiteral(node.left);
        if (leftKey !== null && rightLit !== null) {
          accumulate(leftKey, [rightLit], node);
        } else if (rightKey !== null && leftLit !== null) {
          accumulate(rightKey, [leftLit], node);
        }
      },

      SwitchStatement(node: TSESTree.SwitchStatement): void {
        const key = refKey(node.discriminant);
        if (key === null) {
          return;
        }
        const literals: string[] = [];
        for (const c of node.cases) {
          if (c.test !== null) {
            const lit = strLiteral(c.test);
            if (lit !== null) {
              literals.push(lit);
            }
          }
        }
        if (literals.length > 0) {
          accumulate(key, literals, node);
        }
      },

      TSPropertySignature(node: TSESTree.TSPropertySignature): void {
        collectProperty(
          node.key,
          node.typeAnnotation?.typeAnnotation,
          node.parent,
          node,
        );
      },

      PropertyDefinition(node: TSESTree.PropertyDefinition): void {
        collectProperty(
          node.key,
          node.typeAnnotation?.typeAnnotation,
          node.parent,
          node,
        );
      },

      "Program:exit"(): void {
        for (const clusterNode of validClusters) {
          context.report({
            node: clusterNode,
            messageId: "comparisonCluster",
            data: { key: refKeyText(clusterNode) },
          });
        }
        for (const prop of bareChoiceProps) {
          if (containersWithUnion.has(prop.container)) {
            context.report({
              node: prop.node,
              messageId: "bareChoiceField",
              data: { name: prop.name },
            });
          }
        }
      },
    };

    function refKeyText(node: TSESTree.Node): string {
      if (node.type === AST_NODE_TYPES.BinaryExpression) {
        return refKey(node.left) ?? refKey(node.right) ?? "value";
      }
      if (node.type === AST_NODE_TYPES.SwitchStatement) {
        return refKey(node.discriminant) ?? "value";
      }
      return "value";
    }
  },
});
