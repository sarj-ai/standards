# sarj-ai/linting

Cross-language lint rules for hypermodern TypeScript + Python codebases.

| Package | Tool | Registry | Rules |
|---|---|---|---|
| [`@sarj/eslint-plugin`](packages/eslint-plugin/) | ESLint | [npm](https://www.npmjs.com/package/@sarj/eslint-plugin) | [11](#eslint-rules--sarjeslint-plugin) |
| [`sarj-python-lint`](packages/python-lint/) | pre-commit | [PyPI](https://pypi.org/project/sarj-python-lint/) | [5 AST + 4 SQL](#python--sql-rules--sarj-python-lint) |

**Total: 20 rules.** Each one has a dedicated docs page with bad/good examples, rationale, suppression syntax, and references. Click through the table below.

## ESLint rules — `@sarj/eslint-plugin`

### Foundations (always-on)

| Rule | What it catches |
|---|---|
| [`@sarj/zod-naming-convention`](packages/eslint-plugin/docs/rules/zod-naming-convention.md) | Zod schemas must be named with a `Z` prefix |
| [`@sarj/require-assert-never`](packages/eslint-plugin/docs/rules/require-assert-never.md) | `switch` over a discriminated union must end with `assertNever(_)` |
| [`@sarj/require-zod-form-validation`](packages/eslint-plugin/docs/rules/require-zod-form-validation.md) | `FormData` must be parsed through a Zod schema |
| [`@sarj/enforce-file-structure`](packages/eslint-plugin/docs/rules/enforce-file-structure.md) | Canonical top-of-file order: imports → types → constants → functions → exports |
| [`@sarj/no-raw-env`](packages/eslint-plugin/docs/rules/no-raw-env.md) | `process.env.*` must flow through a Zod-validated env module |
| [`@sarj/prefer-shadcn`](packages/eslint-plugin/docs/rules/prefer-shadcn.md) | Use shadcn/ui primitives instead of native HTML form elements |
| [`@sarj/no-enum`](packages/eslint-plugin/docs/rules/no-enum.md) | TypeScript `enum` is banned; use string literal unions or `as const` |

### Next.js / RSC boundary (added in 1.1.0)

| Rule | What it catches |
|---|---|
| [`@sarj/no-client-side-data-fetching`](packages/eslint-plugin/docs/rules/no-client-side-data-fetching.md) | No `fetch`/`axios` inside `useEffect` |
| [`@sarj/prefer-server-actions`](packages/eslint-plugin/docs/rules/prefer-server-actions.md) | `fetch('/api/*')` mutations should be Server Actions |
| [`@sarj/no-unnecessary-use-client`](packages/eslint-plugin/docs/rules/no-unnecessary-use-client.md) | `'use client'` files with no hooks / events can be RSC |
| [`@sarj/prefer-schema-for-api-payload`](packages/eslint-plugin/docs/rules/prefer-schema-for-api-payload.md) | `response.json()` must flow through a Zod schema parse |

## Python + SQL rules — `sarj-python-lint`

### Python AST

| Code | Rule | What it catches |
|---|---|---|
| `SARJ001` | [`no-sequential-await`](packages/python-lint/docs/rules/no-sequential-await.md) | `for x in xs: await f(x)` — prefer `asyncio.gather` |
| `SARJ002` | [`inefficient-string-concat-in-loop`](packages/python-lint/docs/rules/inefficient-string-concat-in-loop.md) | `s += "..."` inside a loop is O(n²); append + join |
| `SARJ005` | [`prefer-discriminated-union`](packages/python-lint/docs/rules/prefer-discriminated-union.md) | `BaseModel` with `success: bool` + Optionals → `Union[Success, Failure]` |
| `SARJ006` | [`prefer-str-enum`](packages/python-lint/docs/rules/prefer-str-enum.md) | Choice-shaped str field → `StrEnum` (Literal also ok) |

### SQL (Postgres migrations)

| Code | Hook | What it catches |
|---|---|---|
| `SARJ101` | [`sarj-enforce-timestamptz`](packages/python-lint/docs/rules/enforce-timestamptz.md) | `TIMESTAMP` without `WITH TIME ZONE` |
| (pygrep) | [`sarj-ban-postgres-enums`](packages/python-lint/docs/rules/ban-postgres-enums.md) | `CREATE TYPE ... AS ENUM` |
| (pygrep) | [`sarj-ban-create-trigger`](packages/python-lint/docs/rules/ban-create-trigger.md) | `CREATE TRIGGER` |
| (pygrep) | [`sarj-require-if-not-exists-on-create`](packages/python-lint/docs/rules/require-if-not-exists-on-create.md) | `CREATE TABLE` without `IF NOT EXISTS` |
| (pygrep) | [`sarj-prefer-text-over-varchar`](packages/python-lint/docs/rules/prefer-text-over-varchar.md) | `VARCHAR(n)` instead of `TEXT` |

## Why a monorepo?

- One issue tracker, one PR per cross-language rule pair.
- Per-package CI, per-package versioning (`eslint-plugin-vX.Y.Z`, `python-lint-vX.Y.Z` tags).
- Downstream consumers share a single upstream for both ESLint + pre-commit hooks.

## Adding a new rule

- **TypeScript/React/JSX** → `packages/eslint-plugin/lib/rules/<kebab-name>.js` + tests in `tests/rules/` + a docs page in `packages/eslint-plugin/docs/rules/`. Bump `package.json` minor, re-publish.
- **Python or SQL** → `packages/python-lint/src/sarj_python_lint/rules/<snake_name>.py` + test in `tests/rules/` + a docs page in `packages/python-lint/docs/rules/`. Bump `pyproject.toml` minor, tag, publish.

Each new rule must have:
- A clear name (verb-prefix preferred: `no-*`, `prefer-*`, `enforce-*`, `require-*`).
- A docs page following the [Bad / Good / More examples / When to suppress / References] template.
- Tests covering both positive (rule fires) and negative (rule does not fire) cases.
- A `meta` block (ESLint) or `code:` attribute (Python) with a stable error code.

## Quality bar

Every rule in this repo was validated against ~10 real codebases and reviewed by an LLM sensibility judge (Gemini 3.5 Flash) before publication. Rules that produced too many false positives or were too opinionated were dropped or refined before reaching the monorepo. See [analysis/RULE_REVIEW.md](analysis/RULE_REVIEW.md) and [analysis/RULE_REFINEMENT.md](analysis/RULE_REFINEMENT.md) for the verdicts.

## License

MIT.
