import tseslint from "typescript-eslint";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import unicorn from "eslint-plugin-unicorn";
import eslintComments from "@eslint-community/eslint-plugin-eslint-comments";
import zod from "eslint-plugin-zod";
import sarj from "@sarj/eslint-plugin";


/** @type {import("eslint").Linter.Config[]} */
const config = [
  ...tseslint.configs.strictTypeChecked,

  {
    plugins: {
      "@typescript-eslint": tseslint.plugin,
      react,
      "react-hooks": reactHooks,
      unicorn,
      "@eslint-community/eslint-comments": eslintComments,
      zod,
      "@sarj": sarj,
    },
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: process.cwd(),
        ecmaFeatures: { jsx: true },
      },
    },
    settings: { react: { version: "detect" } },
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-non-null-assertion": "error",
      "@typescript-eslint/no-unsafe-assignment": "error",
      "@typescript-eslint/no-unsafe-member-access": "error",
      "@typescript-eslint/no-unsafe-argument": "error",
      "@typescript-eslint/no-unsafe-call": "error",
      "@typescript-eslint/no-unsafe-return": "error",
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/await-thenable": "error",
      "@typescript-eslint/no-misused-promises": "error",
      "@typescript-eslint/require-await": "error",
      "@typescript-eslint/restrict-template-expressions": "error",
      "@typescript-eslint/no-unused-vars": ["error", {
        argsIgnorePattern: "^_",
        varsIgnorePattern: "^_",
        caughtErrorsIgnorePattern: "^_",
        ignoreRestSiblings: true,
      }],
      "@typescript-eslint/consistent-indexed-object-style": ["error", "record"],
      "@typescript-eslint/consistent-type-imports": ["error", {
        prefer: "type-imports",
        fixStyle: "inline-type-imports",
      }],
      "@typescript-eslint/switch-exhaustiveness-check": "error",
      "@typescript-eslint/consistent-type-assertions": ["error", {
        assertionStyle: "never",
        objectLiteralTypeAssertions: "never",
      }],
      "@typescript-eslint/naming-convention": [
        "error",
        { selector: "default", format: ["camelCase"], leadingUnderscore: "allow" },
        { selector: "variable", format: ["camelCase", "UPPER_CASE", "PascalCase"], leadingUnderscore: "allow" },
        { selector: "typeLike", format: ["PascalCase"] },
        { selector: "import", format: ["camelCase", "PascalCase", "UPPER_CASE"] },
        { selector: "objectLiteralProperty", format: null },
        { selector: "typeProperty", format: null },
        { selector: "parameter", format: ["camelCase", "snake_case"], leadingUnderscore: "allow" },
      ],

      "react/jsx-no-leaked-render": ["error", { validStrategies: ["ternary", "coerce"] }],
      "react/no-unstable-nested-components": ["error", { prohibitLocalVariables: true }],
      "react-hooks/exhaustive-deps": "error",
      "react-hooks/rules-of-hooks": "error",
      "react/forbid-elements": ["warn", { forbid: [
        { element: "button",   message: "Use <Button> from your design system." },
        { element: "input",    message: "Use <Input> / <Checkbox> / <RadioGroup> from your design system." },
        { element: "select",   message: "Use <Select> from your design system." },
        { element: "textarea", message: "Use <Textarea> from your design system." },
        { element: "dialog",   message: "Use <Dialog> / <AlertDialog> from your design system." },
        { element: "table",    message: "Use <Table> family from your design system." },
      ]}],

      "unicorn/consistent-function-scoping": "error",
      "unicorn/filename-case": ["error", { cases: { kebabCase: true, pascalCase: true } }],
      "unicorn/prefer-switch": "warn",
      "unicorn/no-array-for-each": "warn",

      "zod/prefer-enum-over-literal-union": "error",

      "@eslint-community/eslint-comments/require-description": ["error", { ignore: [] }],
      "@eslint-community/eslint-comments/no-restricted-disable": ["warn",
        "no-console",
        "react-hooks/exhaustive-deps",
      ],

      "no-restricted-syntax": [
        "error",
        {
          selector: "TSEnumDeclaration",
          message: "Use union types or `as const` objects.",
        },
        {
          selector: "TSModuleDeclaration[kind='namespace']",
          message: "Use ES modules instead of namespaces.",
        },
        {
          selector: "TryStatement > BlockStatement[body.length > 3]",
          message: "Try blocks should not contain more than 3 statements. Isolate the throwing statement.",
        },
      ],
      "no-restricted-properties": ["error", {
        object: "process",
        property: "env",
        message: "Use a Zod-validated env object instead of reading process.env directly.",
      }],
      "no-restricted-imports": ["error", { paths: [
        {
          name: "@clerk/nextjs",
          importNames: ["auth", "currentUser"],
          message: "Prefer an internal user-service wrapper.",
        },
        {
          name: "@clerk/nextjs/server",
          message: "Prefer an internal user-service wrapper.",
        },
      ]}],

      "object-shorthand": ["error", "always"],
      "no-return-await": "error",
      eqeqeq: ["error", "always"],
      "no-await-in-loop": "error",
      "no-param-reassign": "error",
      "array-callback-return": "error",
      "no-fallthrough": "error",
      "no-console": ["error", { allow: ["warn", "error"] }],
      "prefer-const": "error",
      "prefer-template": "error",
      "no-var": "error",
      "no-shadow": "off",
      "@typescript-eslint/no-shadow": "error",

      "@sarj/require-assert-never": "error",
      "@sarj/require-zod-form-validation": "error",
      "@sarj/enforce-file-structure": "warn",
      "@sarj/prefer-schema-for-api-payload": "error",
      "@sarj/no-unnecessary-use-client": "warn",
    },
  },

  {
    files: ["**/*.test.ts", "**/*.test.tsx", "**/__tests__/**/*"],
    rules: {
      "@typescript-eslint/no-unsafe-assignment": "off",
      "@typescript-eslint/no-unsafe-member-access": "off",
      "@typescript-eslint/no-non-null-assertion": "off",
    },
  },

  {
    files: ["**/components/ui/**", "**/components/design-system/**"],
    rules: {
      "react/forbid-elements": "off",
    },
  },

  {
    files: [
      "**/*.config.{ts,tsx,js,jsx,mjs,cjs,mts,cts}",
      "**/scripts/**",
      "**/env/**",
      "**/env.{ts,tsx,js,mjs}",
      "**/server-env.{ts,tsx,js,mjs}",
      "**/client-env.{ts,tsx,js,mjs}",
    ],
    rules: {
      "no-restricted-properties": "off",
    },
  },
];

export default config;
