/**
 * @fileoverview Prefer shadcn/ui form primitives over their native HTML
 * counterparts. Limited to form/dialog elements — `<button>` and `<table>`
 * have been removed from the forbid list because they produced 100% false
 * positives during bulbul validation (icon buttons, layout tables).
 *
 * `<input>` is resolved by its `type`: a bare `<input type="checkbox">` maps to
 * `<Checkbox>`, `radio` → `<RadioGroup>`, `range` → `<Slider>`, and the text-like
 * types (or no type) → `<Input>`. `type="hidden"` is skipped (no shadcn primitive),
 * and a dynamic `type={…}` falls back to the generic `<Input>` rather than asserting
 * a wrong primitive.
 */

import {
  AST_NODE_TYPES,
  ESLintUtils,
  type TSESTree,
} from "@typescript-eslint/utils";

type MessageIds = "preferShadcn";
type Options = readonly [];

const REPLACEMENTS: Readonly<Record<string, string>> = {
  select: "Select",
  textarea: "Textarea",
  dialog: "Dialog",
};

/** `<input type>` → shadcn primitive. Absent types (and text-likes) fall to Input. */
const INPUT_TYPE_REPLACEMENTS: Readonly<Record<string, string>> = {
  checkbox: "Checkbox",
  radio: "RadioGroup",
  range: "Slider",
};

/** `<input type>` values with no shadcn equivalent — never reported. */
const SKIPPED_INPUT_TYPES = new Set<string>(["hidden"]);

const kebabCase = (component: string): string =>
  component.replace(/([a-z0-9])([A-Z])/g, "$1-$2").toLowerCase();

const literalTypeAttr = (
  node: TSESTree.JSXOpeningElement,
): { readonly kind: "literal"; readonly value: string } | { readonly kind: "dynamic" } | null => {
  for (const attribute of node.attributes) {
    if (
      attribute.type !== AST_NODE_TYPES.JSXAttribute ||
      attribute.name.type !== AST_NODE_TYPES.JSXIdentifier ||
      attribute.name.name !== "type"
    ) {
      continue;
    }
    if (attribute.value?.type === AST_NODE_TYPES.Literal && typeof attribute.value.value === "string") {
      return { kind: "literal", value: attribute.value.value.toLowerCase() };
    }
    return { kind: "dynamic" };
  }
  return null;
};

/** Resolve an `<input>` to its shadcn primitive, or null to skip it entirely. */
const resolveInputReplacement = (node: TSESTree.JSXOpeningElement): string | null => {
  const typeAttr = literalTypeAttr(node);
  if (typeAttr === null || typeAttr.kind === "dynamic") return "Input";
  if (SKIPPED_INPUT_TYPES.has(typeAttr.value)) return null;
  return INPUT_TYPE_REPLACEMENTS[typeAttr.value] ?? "Input";
};

export default ESLintUtils.RuleCreator(
  (name) =>
    `https://github.com/sarj-ai/linting/blob/main/packages/typescript/src/rules/${name}.ts`,
)<Options, MessageIds>({
  name: "prefer-shadcn",
  meta: {
    type: "suggestion",
    docs: {
      description:
        "Prefer shadcn/ui form primitives over native `<input>`, `<select>`, `<textarea>`, and `<dialog>` elements.",
    },
    schema: [],
    messages: {
      preferShadcn:
        "Use the shadcn <{{replacement}}> component from @/components/ui/{{lowercase}} instead of native <{{element}}>.",
    },
  },
  defaultOptions: [],
  create(context) {
    return {
      JSXOpeningElement(node: TSESTree.JSXOpeningElement): void {
        // Only lowercase JSXIdentifier names represent native HTML elements.
        // Member expressions (`Foo.Bar`) and namespaces (`svg:path`) are skipped.
        if (node.name.type !== "JSXIdentifier") {
          return;
        }

        const elementName = node.name.name;
        const replacement =
          elementName === "input" ? resolveInputReplacement(node) : REPLACEMENTS[elementName];

        if (replacement === undefined || replacement === null) {
          return;
        }

        context.report({
          node,
          messageId: "preferShadcn",
          data: {
            element: elementName,
            replacement,
            lowercase: kebabCase(replacement),
          },
        });
      },
    };
  },
});
