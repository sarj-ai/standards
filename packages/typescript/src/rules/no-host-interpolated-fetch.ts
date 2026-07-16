/**
 * @fileoverview Flag request URLs (fetch / axios) built from a template
 * literal whose FIRST interpolation lands in the origin position — the
 * `scheme://host[:port]` part before the first `/` that follows the scheme's
 * `//`. A dynamic value in the host position means whoever controls that
 * value controls WHERE the request goes: classic SSRF / request redirection,
 * e.g. `` fetch(`https://${req.query.host}/callback`) `` or
 * `` fetch(`https://${userInput}.example-cdn.com/x`) ``.
 *
 * What is checked:
 *   - `` fetch(`...`) `` and `` fetch(new URL(`...`)) `` (single-argument
 *     `new URL` only — with a second `base` argument the template is a path),
 *   - `` axios.get/post/put/patch/delete/request(`...`) ``.
 *
 * When the template STARTS with the interpolation (`` `${base}/api` ``) it is
 * usually the ubiquitous trusted-base-URL pattern, so it is exempted by NAME:
 * the leading identifier / final member-property / called-function name is
 * allowlisted when it starts with `base|url|origin|host|endpoint|api` or ends
 * with `base|url|origin|host|endpoint|api|uri` (env/config constants such as
 * `env.API_BASE_URL`, `config.apiBase`, `getServiceUrl()`). Any other leading
 * expression is flagged.
 *
 * The same NAME allowlist applies symmetrically to a PLAIN IDENTIFIER in the
 * origin position after a literal scheme: `` fetch(`https://${apiHost}/x`) ``
 * is exempt (locals copied from env/config are overwhelmingly named this
 * way), while `` fetch(`https://${userInput}/x`) `` and
 * `` fetch(`https://${slug}.example.com/x`) `` stay flagged.
 *
 * Regardless of position in the template, an origin-position interpolation is
 * also exempted when it is a MemberExpression whose OBJECT chain contains an
 * identifier or property named `env`, `config`, or `settings` — deployment
 * configuration, not request data (`c.env.POSTHOG_API_HOST`,
 * `process.env.API_HOST`, `config.apiHost`, `settings.host`). Plain member
 * expressions do NOT get the name-based exemption: `req.query.host` /
 * `params.host` — the true-positive shape — stay flagged.
 *
 * KNOWN GAPS (false negatives) — the rule is deliberately conservative:
 *   - All exemptions are name-based, with no data flow. A maliciously-fed
 *     local with a trusted-looking name escapes in BOTH positions:
 *     `` const host = req.query.host; fetch(`${host}/x`) `` and
 *     `` const apiHost = req.query.host; fetch(`https://${apiHost}/x`) `` are
 *     exempted because the identifier name matches the allowlist — the same
 *     trade-off as the leading-position heuristic. Conversely, an env value
 *     copied into a local whose name matches nothing
 *     (`` const h = c.env.API_HOST ``) is still flagged.
 *   - String concatenation (`"https://" + host + "/x"`) and URLs built in a
 *     variable before the call (`` const u = `https://${h}/`; fetch(u) ``)
 *     are not analyzed.
 *   - Template heads without a visible scheme (`` `api.${tld}/x` ``) are
 *     ambiguous and skipped.
 *   - Only bare `fetch` and the `axios.<method>` forms above are matched —
 *     `window.fetch`, axios instances (`client.get(...)`), config-object
 *     forms (`axios.request({ url })`, fetch `Request` objects), and other
 *     HTTP clients (got, ky, undici) are not.
 */

import { ESLintUtils, type TSESTree } from "@typescript-eslint/utils";

type MessageIds = "hostInterpolation";
type Options = readonly [];

const AXIOS_METHODS: ReadonlySet<string> = new Set([
  "get",
  "post",
  "put",
  "patch",
  "delete",
  "request",
]);

const ALLOWLIST_PREFIX = /^(base|url|origin|host|endpoint|api)/i;
const ALLOWLIST_SUFFIX = /(base|url|origin|host|endpoint|api|uri)$/i;

/**
 * Object-chain names that mark a member expression as deployment
 * configuration rather than request data.
 */
const TRUSTED_CONFIG_SOURCES: ReadonlySet<string> = new Set([
  "env",
  "config",
  "settings",
]);

function isAllowlistedName(name: string): boolean {
  return ALLOWLIST_PREFIX.test(name) || ALLOWLIST_SUFFIX.test(name);
}

/**
 * Peels wrappers that don't change which value ends up in the URL:
 * optional chaining, non-null assertions, `as` casts, and `await`.
 */
function unwrapExpression(node: TSESTree.Node): TSESTree.Node {
  let current = node;
  for (;;) {
    switch (current.type) {
      case "ChainExpression":
        current = current.expression;
        break;
      case "TSNonNullExpression":
      case "TSAsExpression":
        current = current.expression;
        break;
      case "AwaitExpression":
        current = current.argument;
        break;
      default:
        return current;
    }
  }
}

/**
 * For a template literal that STARTS with an interpolation, decide whether the
 * leading expression looks like a trusted base-URL constant/getter by name.
 */
function isAllowlistedLeadingExpression(expr: TSESTree.Expression): boolean {
  const node = unwrapExpression(expr);

  if (node.type === "Identifier") {
    return isAllowlistedName(node.name);
  }

  if (node.type === "MemberExpression") {
    const property = node.property;
    if (!node.computed && property.type === "Identifier") {
      return isAllowlistedName(property.name);
    }
    if (
      node.computed &&
      property.type === "Literal" &&
      typeof property.value === "string"
    ) {
      return isAllowlistedName(property.value);
    }
    return false;
  }

  // `${getBaseUrl()}/x` — allow calls whose callee name matches the allowlist.
  if (node.type === "CallExpression") {
    const callee = unwrapExpression(node.callee);
    if (callee.type === "Identifier") {
      return isAllowlistedName(callee.name);
    }
    if (
      callee.type === "MemberExpression" &&
      !callee.computed &&
      callee.property.type === "Identifier"
    ) {
      return isAllowlistedName(callee.property.name);
    }
    return false;
  }

  return false;
}

/**
 * True for a MemberExpression whose OBJECT chain contains an identifier or
 * property named `env`, `config`, or `settings` — deployment configuration
 * rather than request data: `c.env.POSTHOG_API_HOST`, `process.env.API_HOST`,
 * `config.apiHost`, `settings.host`. The FINAL property is deliberately not
 * consulted, so `req.query.host` / `params.host` (request data) do not match.
 */
function isTrustedConfigMember(expr: TSESTree.Expression): boolean {
  const node = unwrapExpression(expr);
  if (node.type !== "MemberExpression") {
    return false;
  }

  // Walk the object chain (everything to the LEFT of the final property).
  let current = unwrapExpression(node.object);
  while (current.type === "MemberExpression") {
    const property = current.property;
    if (
      !current.computed &&
      property.type === "Identifier" &&
      TRUSTED_CONFIG_SOURCES.has(property.name)
    ) {
      return true;
    }
    if (
      current.computed &&
      property.type === "Literal" &&
      typeof property.value === "string" &&
      TRUSTED_CONFIG_SOURCES.has(property.value)
    ) {
      return true;
    }
    current = unwrapExpression(current.object);
  }

  return (
    current.type === "Identifier" && TRUSTED_CONFIG_SOURCES.has(current.name)
  );
}

/**
 * Given the static text BEFORE the first interpolation, returns true when the
 * interpolation lands in the origin (scheme://host[:port]) — i.e. a scheme's
 * `//` (or a protocol-relative `//`) has opened but no path `/` has followed.
 */
function firstInterpolationIsInOrigin(head: string): boolean {
  const schemeIndex = head.indexOf("://");
  if (schemeIndex !== -1) {
    return !head.slice(schemeIndex + 3).includes("/");
  }
  if (head.startsWith("//")) {
    return !head.slice(2).includes("/");
  }
  // No visible scheme: a relative path (`/api/${id}`) or an ambiguous bare
  // host (`api.${tld}/x`). Be conservative and skip.
  return false;
}

/**
 * Returns the URL argument of a matched request call (`fetch(...)` or
 * `axios.<method>(...)`), or undefined when the call is not one we check.
 */
function getRequestUrlArgument(
  node: TSESTree.CallExpression,
): TSESTree.CallExpressionArgument | undefined {
  const callee = node.callee;

  const isFetch = callee.type === "Identifier" && callee.name === "fetch";
  const isAxios =
    callee.type === "MemberExpression" &&
    !callee.computed &&
    callee.object.type === "Identifier" &&
    callee.object.name === "axios" &&
    callee.property.type === "Identifier" &&
    AXIOS_METHODS.has(callee.property.name);

  if (!isFetch && !isAxios) {
    return undefined;
  }

  return node.arguments[0];
}

/**
 * Extracts the template literal that determines the request URL: either the
 * argument itself, or the sole argument of a `new URL(...)` wrapper.
 */
function getUrlTemplate(
  arg: TSESTree.CallExpressionArgument,
): TSESTree.TemplateLiteral | undefined {
  if (arg.type === "TemplateLiteral") {
    return arg;
  }
  if (
    arg.type === "NewExpression" &&
    arg.callee.type === "Identifier" &&
    arg.callee.name === "URL" &&
    arg.arguments.length === 1 &&
    arg.arguments[0]?.type === "TemplateLiteral"
  ) {
    return arg.arguments[0];
  }
  return undefined;
}

export default ESLintUtils.RuleCreator(
  (name) =>
    `https://github.com/sarj-ai/linting/blob/main/packages/typescript/src/rules/${name}.ts`,
)<Options, MessageIds>({
  name: "no-host-interpolated-fetch",
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow request URLs (fetch/axios) whose template literal interpolates a dynamic value into the origin (scheme://host[:port]) position — an SSRF / request-redirection risk.",
    },
    schema: [],
    messages: {
      hostInterpolation:
        "This interpolation lands in the origin (scheme://host[:port]) of the request URL — if the value is user-influenced, it controls where the request goes (SSRF / request redirection). Validate the host against an allowlist, or build the URL with `new URL(path, trustedBase)` and verify `url.origin` before requesting.",
    },
  },
  defaultOptions: [],
  create(context) {
    return {
      CallExpression(node: TSESTree.CallExpression): void {
        const urlArg = getRequestUrlArgument(node);
        if (urlArg === undefined) {
          return;
        }

        const template = getUrlTemplate(urlArg);
        if (template === undefined || template.expressions.length === 0) {
          return;
        }

        const headQuasi = template.quasis[0];
        if (headQuasi === undefined) {
          return;
        }
        // `cooked` is null for invalid escape sequences; fall back to raw.
        const head = headQuasi.value.cooked ?? headQuasi.value.raw;

        const first = template.expressions[0];
        if (first === undefined) {
          return;
        }

        // Regardless of position: env/config/settings member accesses are
        // deployment configuration, not request data.
        if (isTrustedConfigMember(first)) {
          return;
        }

        if (head === "") {
          // Template starts with the interpolation: the extremely common
          // trusted-base-URL pattern — exempt by name, flag otherwise.
          if (!isAllowlistedLeadingExpression(first)) {
            context.report({ node: template, messageId: "hostInterpolation" });
          }
          return;
        }

        if (firstInterpolationIsInOrigin(head)) {
          // Symmetric with the leading-position heuristic: a PLAIN identifier
          // named like a base-URL/host constant (`apiHost`, `serviceUrl`) is
          // config by convention. Member expressions deliberately do NOT get
          // this name exemption (`req.query.host` is the true-positive
          // shape) — they are only exempt via the env/config chain above.
          const firstUnwrapped = unwrapExpression(first);
          if (
            firstUnwrapped.type === "Identifier" &&
            isAllowlistedName(firstUnwrapped.name)
          ) {
            return;
          }
          context.report({ node: template, messageId: "hostInterpolation" });
        }
      },
    };
  },
});
