import enforceFileStructure from "./rules/enforce-file-structure.js";
import noClientSideDataFetching from "./rules/no-client-side-data-fetching.js";
import noCommentCruft from "./rules/no-comment-cruft.js";
import noEnum from "./rules/no-enum.js";
import noInsecureRandomId from "./rules/no-insecure-random-id.js";
import noJsonStringifyError from "./rules/no-json-stringify-error.js";
import noLogOnlyCatch from "./rules/no-log-only-catch.js";
import noRawEnv from "./rules/no-raw-env.js";
import noSentinelReturnOnCatch from "./rules/no-sentinel-return-on-catch.js";
import noSequentialAwait from "./rules/no-sequential-await.js";
import noStringConcatInLoop from "./rules/no-string-concat-in-loop.js";
import noUnnecessaryUseClient from "./rules/no-unnecessary-use-client.js";
import preferDiscriminatedUnion from "./rules/prefer-discriminated-union.js";
import preferSchemaForApiPayload from "./rules/prefer-schema-for-api-payload.js";
import preferSemanticColors from "./rules/prefer-semantic-colors.js";
import preferServerActions from "./rules/prefer-server-actions.js";
import preferShadcn from "./rules/prefer-shadcn.js";
import requireAssertNever from "./rules/require-assert-never.js";
import requireZodFormValidation from "./rules/require-zod-form-validation.js";
import zodNamingConvention from "./rules/zod-naming-convention.js";
import noCorsWildcardWithCredentials from "./rules/no-cors-wildcard-with-credentials.js";
import noFatTryBlocks from "./rules/no-fat-try-blocks.js";
import noSecretInLog from "./rules/no-secret-in-log.js";
import preferStringLiteralUnion from "./rules/prefer-string-literal-union.js";
import singlePublicExport from "./rules/single-public-export.js";

const rules = {
  "enforce-file-structure": enforceFileStructure,
  "no-client-side-data-fetching": noClientSideDataFetching,
  "no-comment-cruft": noCommentCruft,
  "no-enum": noEnum,
  "no-insecure-random-id": noInsecureRandomId,
  "no-json-stringify-error": noJsonStringifyError,
  "no-log-only-catch": noLogOnlyCatch,
  "no-raw-env": noRawEnv,
  "no-sentinel-return-on-catch": noSentinelReturnOnCatch,
  "no-sequential-await": noSequentialAwait,
  "no-string-concat-in-loop": noStringConcatInLoop,
  "no-unnecessary-use-client": noUnnecessaryUseClient,
  "prefer-discriminated-union": preferDiscriminatedUnion,
  "prefer-schema-for-api-payload": preferSchemaForApiPayload,
  "prefer-semantic-colors": preferSemanticColors,
  "prefer-server-actions": preferServerActions,
  "prefer-shadcn": preferShadcn,
  "require-assert-never": requireAssertNever,
  "require-zod-form-validation": requireZodFormValidation,
  "zod-naming-convention": zodNamingConvention,
  "no-cors-wildcard-with-credentials": noCorsWildcardWithCredentials,
  "no-fat-try-blocks": noFatTryBlocks,
  "no-secret-in-log": noSecretInLog,
  "prefer-string-literal-union": preferStringLiteralUnion,
  "single-public-export": singlePublicExport,
};

const plugin = {
  meta: {
    name: "@sarj/eslint-plugin",
    version: "2.3.2",
  },
  rules,
  configs: {
    recommended: {
      plugins: ["@sarj"],
      rules: {
        "@sarj/zod-naming-convention": "warn",
        "@sarj/require-assert-never": "error",
        "@sarj/require-zod-form-validation": "error",
        "@sarj/enforce-file-structure": "warn",
        "@sarj/no-client-side-data-fetching": "warn",
        "@sarj/prefer-server-actions": "warn",
        "@sarj/no-unnecessary-use-client": "warn",
        "@sarj/prefer-schema-for-api-payload": "warn",
        // Distilled from sarj-audit skills — warn in recommended, error in strict.
        "@sarj/no-sequential-await": "warn",
        "@sarj/no-sentinel-return-on-catch": "warn",
        "@sarj/no-log-only-catch": "warn",
        "@sarj/no-insecure-random-id": "warn",
        "@sarj/no-json-stringify-error": "warn",
        "@sarj/no-string-concat-in-loop": "warn",
        "@sarj/prefer-discriminated-union": "warn",
        "@sarj/no-comment-cruft": "warn",
        // Frontend / styling — distilled from frontend PR-review mining.
        "@sarj/prefer-semantic-colors": "warn",
        // Ported from sarj-python-lint (SARJ), corpus-validated FP~0.
        "@sarj/no-fat-try-blocks": "warn",
        "@sarj/no-cors-wildcard-with-credentials": "warn",
        "@sarj/no-secret-in-log": "warn",
        "@sarj/single-public-export": "warn",
        "@sarj/prefer-string-literal-union": "warn",
      },
    },
    strict: {
      plugins: ["@sarj"],
      rules: {
        "@sarj/zod-naming-convention": "error",
        "@sarj/require-assert-never": "error",
        "@sarj/require-zod-form-validation": "error",
        "@sarj/enforce-file-structure": "error",
        "@sarj/no-raw-env": "error",
        "@sarj/prefer-shadcn": "error",
        "@sarj/no-enum": "error",
        "@sarj/no-client-side-data-fetching": "error",
        "@sarj/prefer-server-actions": "error",
        "@sarj/no-unnecessary-use-client": "error",
        "@sarj/prefer-schema-for-api-payload": "error",
        // Distilled from sarj-audit skills.
        "@sarj/no-sequential-await": "error",
        "@sarj/no-sentinel-return-on-catch": "error",
        "@sarj/no-log-only-catch": "error",
        "@sarj/no-insecure-random-id": "error",
        "@sarj/no-json-stringify-error": "error",
        "@sarj/no-string-concat-in-loop": "error",
        "@sarj/prefer-discriminated-union": "error",
        "@sarj/no-comment-cruft": "error",
        // Frontend / styling — distilled from frontend PR-review mining. Stylistic,
        // no autofix → warn (rollout should prove the FP rate before raising it).
        "@sarj/prefer-semantic-colors": "warn",
        // Ported from sarj-python-lint (SARJ), corpus-validated FP~0.
        "@sarj/no-fat-try-blocks": "error",
        "@sarj/no-cors-wildcard-with-credentials": "error",
        "@sarj/no-secret-in-log": "error",
        "@sarj/single-public-export": "error",
        // High-volume/stylistic — warn until rollout proves FP rate.
        "@sarj/prefer-string-literal-union": "warn",
      },
    },
  },
};

export default plugin;
export { rules };
