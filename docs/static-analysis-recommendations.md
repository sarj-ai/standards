# Automating Nasr's code review comments

Synthesis of 10 theme-agent analyses over 5,504 review comments by nmaswood across the sarj-ai GitHub org (2024-06 → 2026-06), cross-checked against `standards_inventory.md` (sarj-ai/standards as of 2026-06-11).

## Executive summary

- **The single biggest win is rollout, not rule-writing.** Roughly a third of all recurring comments (~350+ merged occurrences) are already encoded in `ruff.strict.toml`, `pyright.strict.json`, `eslint.strict.mjs`, `sarj-python-lint`, and `@sarj/eslint-plugin` — but the smaller repos (ai, noura-be, tahded, kashta, summer, tamr, hala, qa-copilot, portal) don't run them, **and bulbul's Python does not use sarj-python-lint or the strict ruff/pyright configs** even though bulbul TS uses `@sarj/eslint-plugin`. A standards-audit bot + required CI checks kills this whole class.
- **Highest-value new rule: a Python "pydantic at every boundary" rule** (port of `@sarj/prefer-schema-for-api-payload` + flag `dict[str, Any]`/tuple returns/untyped route responses). ~146 merged occurrences — his single most common ask.
- **Broaden SARJ006 (prefer_str_enum).** ~113 occurrences, but the current name heuristic (`*_status/_state/_type/_kind`) misses most of his actual hits (`provider`, `language`, `role`, `priority`, …). Cheap extension, huge coverage.
- **A 3-statement try-block rule for Python** (direct port of the existing ESLint `TryStatement > BlockStatement[body.length > 3]`) plus the already-existing ruff BLE001 rollout covers ~90 skinny-try/bubble-up comments.
- **A sarj-sql-lint migration pack (~10 rules)** — idempotent DDL, no PG enums, TEXT+CHECK not VARCHAR, INSERT…ON CONFLICT, no LIMIT/OFFSET, JSONB `'{}'` defaults — mechanizes ~100 comments; his DDL catechism is almost entirely AST-checkable.
- **Three ESLint config one-liners** close ~70 frontend comments: enable `@sarj/no-client-side-data-fetching` + `@sarj/prefer-server-actions` (they exist in the plugin but are NOT in `eslint.strict.mjs`), add a `no-restricted-syntax` ban on `useCallback`/`useMemo`, and tighten `unicorn/filename-case` to kebab-only.
- **Mobile is greenfield**: zero standards coverage for Kotlin/Swift. Enabling detekt/SwiftLint built-ins covers ~60 comments immediately; a small `sarj-detekt-rules` port of SARJ005/006/assert-never/try-size covers ~70 more.
- **~600 occurrences are judgment calls** (YAGNI deletion, redundant comments, "why is this nullable?", layering, index justification) — these need an auto-invoked LLM reviewer (he manually summons `@claude` today, 28×). A ready-to-paste review-bot prompt is in Tier 4.

> **Update — redundancy trim (build-vs-adopt audit).** A later audit found several
> rules duplicated tooling we already run, so they were deleted in favor of the
> off-the-shelf equivalent: `@sarj/no-raw-env` → the config's `no-restricted-properties`
> ban on `process.env`; `@sarj/no-sequential-await` → core `no-await-in-loop`;
> `@sarj/prefer-shadcn` → `react/forbid-elements`; `sarj-python-lint`'s
> `no_unreachable_after_terminal` → basedpyright `reportUnreachable`; and four
> `sarj-sql-lint` migration rules (`enforce_timestamptz`, `idempotent_ddl`,
> `index_concurrently`, `prefer_text_over_varchar`) → **squawk** (`prefer-timestamptz`,
> `prefer-robust-stmts`, `require-concurrent-index-creation`, `prefer-text-field`), the
> parser-based migration linter consumers already run. The Tier-3 entries below that
> proposed those rules are kept for the historical record.

## Methodology

- Corpus: 5,504 comments split into 10 slices: `py-app-1..4` (~3,211 Python application comments), `py-tests` (47), `ts-frontend` (714), `ts-backend` (511), `sql-infra-config` (297), `mobile` (244, all noura-fe), `general-reviews` (480 PR-level/process).
- Each slice agent extracted recurring patterns with per-slice frequency counts and categorized them (already-covered / off-the-shelf / new-custom-rule / not-statically-checkable).
- This report **deduplicates across slices** — the four py-app slices report the same themes, so frequencies below are **sums of per-slice counts**. They are approximate occurrence counts, not exact: slice agents counted independently and some comments match multiple patterns.
- Every "already-covered" claim was re-verified against `standards_inventory.md`; several agent claims were re-tiered (e.g. `@sarj/no-client-side-data-fetching` exists in the plugin but is absent from `eslint.strict.mjs` → moved to Tier 2 config change).

## Tier 1 — Adopt existing tooling (highest ROI)

These rules **already exist** in sarj-ai/standards. The comments keep recurring only because the reviewed repos don't run the configs. Note: bulbul TS already uses `@sarj/eslint-plugin`, but **bulbul Python does NOT use `sarj-python-lint` or `ruff.strict.toml`/`pyright.strict.json`** — adoption starts at home.

**Adoption plan (one effort, kills every row below):**
1. Adopt `ruff.strict.toml` + `pyright.strict.json` + `sarj-python-lint` + `sarj-sql-lint` in bulbul Python, ai, noura-be, tahded, kashta, summer, automations, wiki.
2. Adopt `eslint.strict.mjs` + `@sarj/eslint-plugin` in summer, kashta, tamr, hala, tahded, noura-be, qa-copilot, portal, ai-canvas-health.
3. Make `ruff check` / `ruff format --check` / `eslint --max-warnings 0` / `prettier --check` **required** GitHub status checks org-wide.
4. Stand up a scheduled "standards-audit" workflow that scans every sarj-ai repo for the shared configs + CI gates and opens a scaffolding PR when missing.

| Pattern | Freq | Existing rule | Adoption action |
|---|---|---|---|
| No blind/bare except, no swallow, let errors bubble (Py) | ~49 | ruff `BLE001`, `E722`, `S110`/`S112`, `TRY302`/`TRY400` (select=ALL) | Roll out ruff.strict.toml ([ex1](https://github.com/sarj-ai/bulbul/pull/727#discussion_r2176106401), [ex2](https://github.com/sarj-ai/bulbul/pull/56#discussion_r1847102697)) |
| Modern typing: `T \| None`, `dict`/`list`, snake_case | ~58 | ruff `UP006/UP007/UP035/UP045`, `N8xx`; pyright `deprecateTypingAliases` | Roll out ([ex1](https://github.com/sarj-ai/bulbul/pull/329#discussion_r2031600927), [ex2](https://github.com/sarj-ai/ai/pull/2#discussion_r2255651990)) |
| Skinny try blocks (TS) | ~42 | eslint.strict.mjs `no-restricted-syntax` `TryStatement > BlockStatement[body.length > 3]` | Adopt strict config in ts-backend repos ([ex1](https://github.com/sarj-ai/summer/pull/55#discussion_r1707100706), [ex2](https://github.com/sarj-ai/tamr/pull/2#discussion_r2003867960)) |
| No `as` casts (TS) | ~33 | `@typescript-eslint/consistent-type-assertions` assertionStyle:"never" | Adopt ([ex1](https://github.com/sarj-ai/bulbul/pull/342#discussion_r2037526250), [ex2](https://github.com/sarj-ai/portal/pull/25#discussion_r2780003654)) |
| No `any` (TS) | ~32 | `@typescript-eslint/no-explicit-any` + `no-unsafe-*` family | Adopt ([ex1](https://github.com/sarj-ai/summer/pull/55#discussion_r1707249837), [ex2](https://github.com/sarj-ai/tamr/pull/16#discussion_r2312115147)) |
| print/loguru basics, f-string logs | ~30 | ruff `T201`, `G004`, `LOG015` | Roll out; see Tier 2 for `logging.getLogger` ban ([ex1](https://github.com/sarj-ai/bulbul/pull/865#discussion_r2217485961), [ex2](https://github.com/sarj-ai/kashta/pull/43#discussion_r2093722172)) |
| switch + assertNever exhaustiveness (TS) | ~17 | `@sarj/require-assert-never` + `switch-exhaustiveness-check` | Adopt ([ex1](https://github.com/sarj-ai/bulbul/pull/35#discussion_r1835509427), [ex2](https://github.com/sarj-ai/tamr/pull/16#discussion_r2312115462)) |
| "Run the formatter/linter" comments | ~15 | configs exist; nothing enforces them | Required CI checks + pre-commit org-wide ([ex1](https://github.com/sarj-ai/bulbul/pull/27#discussion_r1831468493), [ex2](https://github.com/sarj-ai/tamr/pull/2#discussion_r2003898674)) |
| Settings via pydantic/Zod, no raw env | ~12 | ruff banned-api `os.environ`/`os.getenv` (TID251); `no-restricted-properties` process.env | Roll out ([ex1](https://github.com/sarj-ai/kashta/pull/41#discussion_r2093269795), [ex2](https://github.com/sarj-ai/qa-copilot/pull/4#discussion_r2760437285)) |
| No TS `enum` / nativeEnum | ~11 | `@sarj/no-enum` + `TSEnumDeclaration` restricted-syntax | Adopt; Tier 2 adds `z.nativeEnum` ban ([ex1](https://github.com/sarj-ai/bulbul/pull/655#discussion_r2155433629), [ex2](https://github.com/sarj-ai/bulbul/pull/793#discussion_r2189768805)) |
| Function-level imports → top | ~8 | ruff `PLC0415` (preview, select=ALL) | Roll out ([ex1](https://github.com/sarj-ai/ai/pull/16#discussion_r2433829347), [ex2](https://github.com/sarj-ai/kashta/pull/45#discussion_r2094677530)) |
| `success: bool` + Optional fields → Result union (narrow shape) | part of ~88 | sarj-python-lint `SARJ005` | **Install sarj-python-lint in bulbul** ([ex1](https://github.com/sarj-ai/bulbul/pull/564#discussion_r2114517314), [ex2](https://github.com/sarj-ai/ai/pull/2#discussion_r2255653372)) |
| String `+=` in loop (Py) | ~5 | sarj-python-lint `SARJ002` | Install ([ex1](https://github.com/sarj-ai/bulbul/pull/53#discussion_r1845314610), [ex2](https://github.com/sarj-ai/noura-be/pull/150#discussion_r2285655129)) |
| `bare eslint-disable` needs reason | ~5 | `eslint-comments/require-description` | Adopt on bulbul app package ([ex1](https://github.com/sarj-ai/bulbul/pull/1906#discussion_r2736659429), [ex2](https://github.com/sarj-ai/bulbul/pull/1926#discussion_r2750601786)) |
| Mock/AsyncMock ban in tests | ~4 | ruff banned-api `unittest.mock.*` (TID251) + bulbul pre-commit hook | Already live in bulbul; roll out elsewhere ([ex1](https://github.com/sarj-ai/bulbul/pull/2851#discussion_r3219038772), [ex2](https://github.com/sarj-ai/bulbul/pull/268#discussion_r2027205985)) |
| Upload via pre-signed URL | ~4 | ruff banned-api `fastapi.UploadFile` | Roll out ([ex1](https://github.com/sarj-ai/kashta/pull/45#discussion_r2094676468), [ex2](https://github.com/sarj-ai/automations/pull/72#discussion_r3178871422)) |
| Leaked `{0 &&}` JSX render | ~4 | `react/jsx-no-leaked-render` | Adopt ([ex1](https://github.com/sarj-ai/bulbul/pull/721#discussion_r2172630051), [ex2](https://github.com/sarj-ai/bulbul/pull/795#discussion_r2189779062)) |
| Sequential awaits → Promise.all / gather | ~3 (TS), Py via SARJ001 | core `no-await-in-loop`; sarj-python-lint `SARJ001` | Adopt/install ([ex1](https://github.com/sarj-ai/summer/pull/44#discussion_r1678859692), [ex2](https://github.com/sarj-ai/summer/pull/55#discussion_r1707237429)) |
| No to_camel aliasing in backend | ~3 | ruff banned-api `pydantic.alias_generators.to_camel` | Roll out ([ex1](https://github.com/sarj-ai/bulbul/pull/580#pullrequestreview-2889739556), [ex2](https://github.com/sarj-ai/bulbul/pull/1169#pullrequestreview-3171209799)) |

## Tier 2 — Off-the-shelf rules to enable

Exact config changes; no new rule code.

### Python — `ruff.strict.toml` additions

| Pattern | Freq | Exact config change |
|---|---|---|
| loguru not stdlib logging | ~30 (merged w/ Tier 1 loguru) | Add banned-api: `"logging.getLogger".msg = "Use loguru (from loguru import logger)."` and `"logging.basicConfig".msg = "Use loguru."` ([ex1](https://github.com/sarj-ai/bulbul/pull/564#discussion_r2108925620), [ex2](https://github.com/sarj-ai/noura-be/pull/5#discussion_r2099124599)) |
| No load_dotenv | ~3 | banned-api `"dotenv.load_dotenv".msg = "Use a pydantic-settings BaseSettings class."` ([ex](https://github.com/sarj-ai/bulbul/pull/27#discussion_r1831466547)) |
| No sys.path / importlib hacks in tests | ~3 | banned-api `"sys.path"` + `"importlib.util.spec_from_file_location"` → "install the package; run `uv run pytest`" ([ex1](https://github.com/sarj-ai/noura-be/pull/283#discussion_r2392544004), [ex2](https://github.com/sarj-ai/noura-be/pull/283#discussion_r2392547925)) |
| Hardcoded credentials | ~5 | Un-ignore `S105`/`S106` for non-test code; add **gitleaks** pre-commit hook ([ex1](https://github.com/sarj-ai/kashta/pull/45#discussion_r2094675449), [ex2](https://github.com/sarj-ai/bulbul/pull/727#discussion_r2176107553)) |

### TypeScript — `eslint.strict.mjs` changes

| Pattern | Freq | Exact config change |
|---|---|---|
| Server-first data fetching | ~34 | **Enable `@sarj/no-client-side-data-fetching` and `@sarj/prefer-server-actions` as "error"** (exist in plugin, absent from config); raise `@sarj/no-unnecessary-use-client` warn→error ([ex1](https://github.com/sarj-ai/bulbul/pull/268#discussion_r2013023500), [ex2](https://github.com/sarj-ai/kashta/pull/45#discussion_r2094679531)) |
| No useCallback/useMemo without profiling | ~25 | `no-restricted-syntax`: `CallExpression[callee.name=/^(useCallback\|useMemo)$/]` → "Avoid unless profiling shows a win; disable-with-reason if needed" ([ex1](https://github.com/sarj-ai/bulbul/pull/853#discussion_r2220597876), [ex2](https://github.com/sarj-ai/bulbul/pull/1564#discussion_r2536539119)) |
| forEach / index loops → for-of/map | ~12 | `unicorn/no-array-for-each` warn→**error**; add `unicorn/no-for-loop` ([ex1](https://github.com/sarj-ai/bulbul/pull/608#discussion_r2134740403), [ex2](https://github.com/sarj-ai/summer/pull/55#discussion_r1707186794)) |
| useEffect for derived/event state | ~11 | Add `eslint-plugin-react-you-might-not-need-an-effect` (no-derived-state, no-event-handler, no-chain-state-updates) at error ([ex1](https://github.com/sarj-ai/bulbul/pull/581#discussion_r2124429135), [ex2](https://github.com/sarj-ai/bulbul/pull/1650#discussion_r2595234939)) |
| kebab-case filenames | ~8 | `unicorn/filename-case` → `["error", { cases: { kebabCase: true } }]` (drop pascalCase — it permits exactly the files he flags) ([ex1](https://github.com/sarj-ai/summer/pull/60#discussion_r1712662344), [ex2](https://github.com/sarj-ai/bulbul/pull/721#discussion_r2172963089)) |
| No `in` operator | ~7 | `no-restricted-syntax`: `BinaryExpression[operator='in']` → "Use Object.hasOwn / tag-field check" ([ex1](https://github.com/sarj-ai/bulbul/pull/608#discussion_r2136348114), [ex2](https://github.com/sarj-ai/bulbul/pull/853#discussion_r2217084763)) |
| Import sorting | ~3 | Add `eslint-plugin-simple-import-sort` ([ex](https://github.com/sarj-ai/tamr/pull/2#discussion_r2004737556)) |
| z.nativeEnum ban | part of 11 | `no-restricted-syntax`: `CallExpression[callee.object.name='z'][callee.property.name='nativeEnum']` ([ex](https://github.com/sarj-ai/bulbul/pull/655#discussion_r2155433629)) |

### Mobile (Kotlin/Swift) — new configs, built-in rules only

No sarj standards exist for mobile. Create shared `detekt.strict.yml` + `.swiftlint.yml` and enforce in noura-fe CI:

| Pattern | Freq | Exact config change |
|---|---|---|
| Don't swallow exceptions | ~11 | detekt `TooGenericExceptionCaught`, `SwallowedException`, `EmptyCatchBlock`; SwiftLint custom regex `swallowed_error` ([ex1](https://github.com/sarj-ai/noura-fe/pull/22#discussion_r2143632888), [ex2](https://github.com/sarj-ai/noura-fe/pull/37#discussion_r2296902140)) |
| Extract components / flatten nesting | ~16 | detekt `LargeClass`, `LongMethod`, `NestedBlockDepth`; SwiftLint `type_body_length`, `function_body_length` ([ex1](https://github.com/sarj-ai/noura-fe/pull/2#discussion_r2094657615), [ex2](https://github.com/sarj-ai/noura-fe/pull/33#discussion_r2274658683)) |
| Magic numbers / inline hex colors | ~12 | detekt `MagicNumber` (ignoreAnnotated: Preview); SwiftLint `no_magic_numbers` + color-literal regex ([ex1](https://github.com/sarj-ai/noura-fe/pull/19#discussion_r2136740159), [ex2](https://github.com/sarj-ai/noura-fe/pull/55#discussion_r2386334073)) |
| kotlinx.serialization not org.json | ~8 | detekt `ForbiddenImport`: `org.json.JSONObject/JSONArray`; `ForbiddenMethodCall`: `optString/optLong` ([ex1](https://github.com/sarj-ai/noura-fe/pull/15#discussion_r2118320336), [ex2](https://github.com/sarj-ai/noura-fe/pull/37#discussion_r2296901521)) |
| Duration/Instant types | ~7 | detekt `ForbiddenImport`: `java.util.Date`; rest is Tier 3 custom ([ex1](https://github.com/sarj-ai/noura-fe/pull/15#discussion_r2118328302), [ex2](https://github.com/sarj-ai/noura-fe/pull/8#discussion_r2107587839)) |
| SDK logger not Log/println | ~4 | detekt `ForbiddenMethodCall`: `android.util.Log.*`, `kotlin.io.println`; SwiftLint `print(` regex ([ex1](https://github.com/sarj-ai/noura-fe/pull/27#discussion_r2224186109), [ex2](https://github.com/sarj-ai/noura-fe/pull/33#discussion_r2274657473)) |
| Formatting gate | ~2 | ktlint `--check` + SwiftFormat `--lint` as required CI checks ([ex](https://github.com/sarj-ai/noura-fe/pull/51#discussion_r2342778500)) |

### CI / process — off-the-shelf actions & tools

| Pattern | Freq | Exact change |
|---|---|---|
| Auto-invoke LLM reviewer | ~28 | `anthropics/claude-code-action` with `on: pull_request [opened, ready_for_review]` org-wide, prompt seeded with Tier 4 checklist ([ex1](https://github.com/sarj-ai/bulbul/pull/615#issuecomment-2957448173), [ex2](https://github.com/sarj-ai/ai/pull/113#pullrequestreview-4052649888)) |
| Linear ticket in PR title | ~15 | `amannn/action-semantic-pull-request` with headerPattern `^\[(SARJ\|PLT\|NOURA)-\d+\]\s+.+` (or branch-name ticket fallback) ([ex1](https://github.com/sarj-ai/bulbul/pull/24#issuecomment-2458597109), [ex2](https://github.com/sarj-ai/noura-be/pull/249#pullrequestreview-3214353294)) |
| Justify every dependency | ~14 | `knip` (TS) + `deptry` (Py) in CI — fails on declared-but-unimported deps ([ex1](https://github.com/sarj-ai/bulbul/pull/199#discussion_r1938429895), [ex2](https://github.com/sarj-ai/tahded/pull/4#discussion_r2217061488)) |
| No committed artifacts/large files | ~10 | pre-commit `check-added-large-files --maxkb=1024` + deny-glob hook (`*.whl`, `*.bak`, `dist/**`, `*.egg-info/**`) ([ex1](https://github.com/sarj-ai/summer/pull/8#discussion_r1659080213), [ex2](https://github.com/sarj-ai/tahded/pull/19#discussion_r2261038110)) |
| Versions current, no pins/downgrades | ~10 | Renovate org-wide + CI grep for `==` pins in pyproject deps ([ex1](https://github.com/sarj-ai/bulbul/pull/158#discussion_r1922789695), [ex2](https://github.com/sarj-ai/summer/pull/119#discussion_r2328837283)) |
| uv/ruff/3.13+ toolchain bootstrap | ~9 | Reusable "sarj-python-bootstrap" workflow: fail on requirements.txt, missing uv.lock, missing [tool.ruff], old .python-version ([ex1](https://github.com/sarj-ai/ai/pull/113#discussion_r3029924469), [ex2](https://github.com/sarj-ai/tahded/pull/14#discussion_r2229631888)) |
| Terraform hygiene | ~6 | `tflint` with `terraform_unused_declarations` on iac/** ([ex1](https://github.com/sarj-ai/noura-be/pull/28#discussion_r2157735175), [ex2](https://github.com/sarj-ai/noura-iac/pull/7#discussion_r2199018387)) |
| Tests before merge / placeholder test files | ~6 | Codecov/diff-cover patch-coverage gate on changed lines; fail when a new tests/**/test_*.py has no `def test_` ([ex1](https://github.com/sarj-ai/bulbul/pull/395#pullrequestreview-2797820325), [ex2](https://github.com/sarj-ai/bulbul/pull/268#discussion_r2023462691)) |
| PR evidence (screenshots/looms) | ~5 | Danger-style action: UI paths touched + no image/loom in body → comment ([ex1](https://github.com/sarj-ai/summer/pull/53#pullrequestreview-2213885796), [ex2](https://github.com/sarj-ai/bulbul/pull/1927#pullrequestreview-3735032602)) |

## Tier 3 — New custom rules worth building

Ranked by merged frequency × feasibility. Example URLs double as test-case sources.

### sarj-python-lint

1. **SARJ010 `pydantic_at_boundaries`** (~146) — Python port of `@sarj/prefer-schema-for-api-payload` plus payload-shape checks: (a) track vars from `resp.json()`/`json.loads()`; flag subscript/`.get()` access without an interposed `Model.model_validate`; (b) flag `dict[str, Any]`/bare `dict`/heterogeneous `tuple[...]` in public function returns, params, and pydantic fields outside tests/scripts; (c) flag FastAPI route handlers returning `dict`/`list[dict]`/dict literals → "define a pydantic response model"; (d) in `**/stores/**`, flag cursors without `row_factory=class_row(Model)` whose rows feed model constructors. ([ex1](https://github.com/sarj-ai/bulbul/pull/496#discussion_r2083601642), [ex2](https://github.com/sarj-ai/bulbul/pull/724#discussion_r2172978403), [ex3](https://github.com/sarj-ai/wiki/pull/1#discussion_r3139433978))
2. **Extend SARJ006 `prefer_str_enum`** (~113) — broaden name list to `language|provider|priority|voice|gender|role|model|status|format|dialect|currency|code|direction`; also trigger on (a) str field with closed-set-looking literal default (`priority: str = "High"`), (b) a str var compared (`==`/`in`) against ≥2 distinct string literals in the same module. Add numeric sibling: bare `int`/`float` pydantic fields named `count|limit|attempts|size|*_rate` without `Field(ge/le)` → suggest `NonNegativeInt`/`PositiveInt`. ([ex1](https://github.com/sarj-ai/ai/pull/6#discussion_r2335043870), [ex2](https://github.com/sarj-ai/bulbul/pull/727#discussion_r2176104188), [ex3](https://github.com/sarj-ai/noura-be/pull/161#discussion_r2296333955))
3. **Extend SARJ005 `prefer_discriminated_union`** (~88) — new triggers: (a) BaseModel with ≥3 sibling `X | None = None` fields; (b) `error: str | None` + ≥1 optional payload field; (c) function returning `tuple[bool, T | None]`; (d) function annotated `-> bool` returning True in try / False in except. Message: model as Literal-tagged Success | Failure union. ([ex1](https://github.com/sarj-ai/bulbul/pull/737#discussion_r2176057740), [ex2](https://github.com/sarj-ai/tahded/pull/14#discussion_r2234404460))
4. **SARJ013/014 `prefer_match` + `require_assert_never_in_wildcard`** (~67) — (a) if/elif chains (≥2 elif) testing the same name via `isinstance`/`==` literals → "use match/case"; (b) `match` whose `case _:` body doesn't call `typing.assert_never` or raise → flag. Closes the hole where `case _:` silences pyright `reportMatchNotExhaustive`. ([ex1](https://github.com/sarj-ai/bulbul/pull/574#discussion_r2121855856), [ex2](https://github.com/sarj-ai/bulbul/pull/1255#discussion_r2350299324))
5. **SARJ015 `fat_try_block`** (~39) — flag `ast.Try` body > 3 statements (direct port of the ESLint rule); exempt tests/scripts. Pair with a check for except handlers whose body is only log + `return constant`/`pass` → "don't swallow; bubble up". ([ex1](https://github.com/sarj-ai/ai/pull/4#discussion_r2260981209), [ex2](https://github.com/sarj-ai/bulbul/pull/2598#discussion_r3098021806))
6. **SARJ021 `hoist_constant`** (~35) — int/float literals (outside {-1,0,1,2,10,100}) as call args/operands, and parameter-independent list/dict/tuple literals built inside function bodies → "hoist to module-level UPPER_CASE constant". Complements PLR2004 (comparisons only). Nasr: "NOTE TO SELF, find a linting rule for this." ([ex1](https://github.com/sarj-ai/ai/pull/6#discussion_r2328787960), [ex2](https://github.com/sarj-ai/bulbul/pull/1275#discussion_r2366437894))
7. **SARJ016 `prefer_timedelta`** (~30) — int/float params/fields/constants named `(timeout|ttl|duration|delay|interval|expir|_seconds|_ms|_minutes|_hours)` or assigned `60*X` arithmetic → "use datetime.timedelta" (already CLAUDE.md house style, zero enforcement). ([ex1](https://github.com/sarj-ai/bulbul/pull/616#discussion_r2138321439), [ex2](https://github.com/sarj-ai/noura-be/pull/243#discussion_r2341834133))
8. **SARJ018 `require_keyword_only`** (~26) — FunctionDef with ≥2 same-annotated positional params (or ≥4 total) and no `*` marker → autofix-insert `*,` after self. Bool half already covered by FBT001-003. ([ex1](https://github.com/sarj-ai/bulbul/pull/597#discussion_r2121843303), [ex2](https://github.com/sarj-ai/bulbul/pull/826#discussion_r2199008079))
9. **SARJ017 `prefer_walrus`** (~24) — `x = expr` immediately followed by `if x:` / `if not x:` where x is unused afterward → autofix `if x := expr:`. No ruff equivalent. ([ex1](https://github.com/sarj-ai/bulbul/pull/876#discussion_r2229569647), [ex2](https://github.com/sarj-ai/bulbul/pull/603#discussion_r2124309460))
10. **SARJ022 `inline_trivial_helper`** (~12) — private function ≤2 statements referenced exactly once in the module → "inline it"; exempt ABC overrides/properties/callbacks. ([ex1](https://github.com/sarj-ai/bulbul/pull/496#discussion_r2085487462), [ex2](https://github.com/sarj-ai/bulbul/pull/1138#discussion_r2296795883))
11. **`no_fake_when_real_impl_exists`** (~6, tests) — `Fake*/InMemory*` class in tests subclassing ABC B when a `Psql*`/emulator impl of B exists → "use the real fixture". ([ex1](https://github.com/sarj-ai/bulbul/pull/2851#discussion_r3230088982), [ex2](https://github.com/sarj-ai/bulbul/pull/3017#discussion_r3295767747))
12. **`no_redefined_canonical_type`** (~7) — redefinition of allowlisted brands (`CallId`, `Language`, `StringUUID`, …) outside their canonical module → "import it". ([ex1](https://github.com/sarj-ai/bulbul/pull/708#discussion_r2172973223), [ex2](https://github.com/sarj-ai/bulbul/pull/737#discussion_r2176058550))

### sarj-sql-lint (migration + store pack, ~100 merged)

13. **SARJ102 `require_idempotent_ddl`** (18) — CREATE TABLE/INDEX, ADD COLUMN, DROP without `IF [NOT] EXISTS` in `svcs/db/db/migrations/**`. ([ex1](https://github.com/sarj-ai/bulbul/pull/276#discussion_r2017009937), [ex2](https://github.com/sarj-ai/bulbul/pull/1572#discussion_r2536635391))
14. **SARJ103 `insert_requires_on_conflict`** (~39 incl. store upsert asks) — `INSERT INTO` without `ON CONFLICT` in migrations and `**/stores/**` SQL strings; inline `-- append-only` suppression. ([ex1](https://github.com/sarj-ai/bulbul/pull/782#discussion_r2187894790), [ex2](https://github.com/sarj-ai/automations/pull/72#discussion_r3178868635))
15. **SARJ104 `no_limit_offset`** (~10) — flag `OFFSET` → "cursor pagination". Plus `no_select_distinct`, `no_unbounded_select`, leading-wildcard `ILIKE '%…'`. ([ex1](https://github.com/sarj-ai/bulbul/pull/737#discussion_r2176061242), [ex2](https://github.com/sarj-ai/bulbul/pull/1072#discussion_r2276866226))
16. **SARJ105/106 `text_with_check_not_varchar`** (13) — flag VARCHAR; flag TEXT without `CHECK(char_length...)`; flag count/duration ints without `CHECK (>= 0)`. ([ex1](https://github.com/sarj-ai/tahded/pull/4#discussion_r2217062546), [ex2](https://github.com/sarj-ai/bulbul/pull/450#discussion_r2072428060))
17. **SARJ107-112 small rules** — `no_pg_enum` (7, [ex](https://github.com/sarj-ai/bulbul/pull/268#discussion_r2013022294)); `jsonb_default_object` not `'[]'` (5, [ex](https://github.com/sarj-ai/bulbul/pull/491#discussion_r2078813766)); `app_layer_validation` — no triggers/plpgsql/regex CHECKs (6, [ex](https://github.com/sarj-ai/bulbul/pull/2760#discussion_r3218954476)); `no_business_default` (5, [ex](https://github.com/sarj-ai/bulbul/pull/792#discussion_r2203737540)); `prefer_status_text` over boolean flags (4, [ex](https://github.com/sarj-ai/bulbul/pull/1001#discussion_r2257696376)); `duration_ms_not_seconds` (3); `no_comment_on` (3); redundant-prefix-index detection (subset of 24).

### @sarj/eslint-plugin

18. **Extend `prefer-schema-for-api-payload` → `require-zod-at-boundaries`** (~45) — also track `formData.get()`, `searchParams`, `localStorage.getItem`, `JSON.parse`, route `params`, ky/axios `.json<T>()`. ([ex1](https://github.com/sarj-ai/bulbul/pull/493#discussion_r2078816176), [ex2](https://github.com/sarj-ai/qa-copilot/pull/4#discussion_r2760438370))
19. **`require-camelcase-domain-shape`** (~31) — implement/document `zod-naming-convention` (exists, undocumented, not in config): snake_case keys in exported z.object()/interfaces without a `.transform()` boundary → "convert to camelCase at the Zod boundary". The FE half of the to_camel ban. ([ex1](https://github.com/sarj-ai/bulbul/pull/450#discussion_r2072428785), [ex2](https://github.com/sarj-ai/bulbul/pull/268#discussion_r2013030599))
20. **`prefer-module-scope-constants` / `hoist-static-component-values`** (~29) — pure-literal `const` (object/array/template/zod schema) inside a function/component referencing no local bindings → hoist + UPPER_CASE. ([ex1](https://github.com/sarj-ai/kashta/pull/4#discussion_r2001073937), [ex2](https://github.com/sarj-ai/tamr/pull/2#discussion_r2003864890))
21. **`no-accumulating-spread` + `no-string-concat-in-loop`** (~17) — TS twin of SARJ002: `acc = [...acc, x]` in loops / reduce; string `+=` in loops (type-aware). ([ex1](https://github.com/sarj-ai/bulbul/pull/581#discussion_r2118304791), [ex2](https://github.com/sarj-ai/hala/pull/79#discussion_r2072433381))
22. **`prefer-literal-union` / `prefer-zod-enum`** (~17) — TS twin of SARJ006: `z.string()` or `: string` on members named `/(type|status|state|mode|kind|category|role|provider)$/` → literal union / z.enum. ([ex1](https://github.com/sarj-ai/summer/pull/60#discussion_r1712661503), [ex2](https://github.com/sarj-ai/hala/pull/126#discussion_r2271649348))
23. **`prefer-discriminated-union`** (TS twin of SARJ005, ~10) — `success: boolean` + optional members in interfaces/z.object. ([ex1](https://github.com/sarj-ai/bulbul/pull/348#discussion_r2040758473), [ex2](https://github.com/sarj-ai/bulbul/pull/1081#discussion_r2283508647))
24. **Smaller rules**: `no-optional-and-nullable` zod (9, [ex](https://github.com/sarj-ai/bulbul/pull/1330#discussion_r2403655584)); `prefer-use-transition` over manual isLoading state (8, [ex](https://github.com/sarj-ai/bulbul/pull/697#discussion_r2167603391)); `sql-template-hygiene` for slonik (no SELECT *, LIMIT required, upsert) (8, [ex](https://github.com/sarj-ai/tamr/pull/3#discussion_r2010333478)); `no-util-files` (8, [ex](https://github.com/sarj-ai/bulbul/pull/581#discussion_r2127890222)); `no-render-helper-functions` (7, [ex](https://github.com/sarj-ai/summer/pull/55#discussion_r1707262274)); `prefer-guard-clause` (5); `no-dispatch-prop` (3).

### semgrep pack (cross-cutting)

25. **`no-client-construction-in-service`** (~67) — `httpx.AsyncClient()`, `boto3.client()`, `genai.Client()`, `OpenAI()`, `Settings()` instantiation inside class methods of `services/`/`stores/`/`integrations/` (excluding main.py/create_app/conftest) → "inject via __init__ from the composition root". ([ex1](https://github.com/sarj-ai/bulbul/pull/564#discussion_r2109637254), [ex2](https://github.com/sarj-ai/bulbul/pull/616#discussion_r2141357956))
26. **`llm-require-structured-output`** (~26, Py+TS) — `json.loads`/regex on LLM SDK response text when the call lacks `response_format`/`response_schema`/`tools` → "pass a pydantic/Zod schema via structured outputs". ([ex1](https://github.com/sarj-ai/bulbul/pull/501#discussion_r2084868212), [ex2](https://github.com/sarj-ai/summer/pull/44#discussion_r1678860574))
27. **`no-sync-sdk-in-async`** (~15 residual) — sync boto3/genai/resend calls inside `async def` not covered by ruff ASYNC2xx → "use the async client or asyncio.to_thread"; plus `BackgroundTasks.add_task`/bare threads in Cloud Run webserver paths → "use Cloud Tasks/PubSub". ([ex1](https://github.com/sarj-ai/bulbul/pull/1406#discussion_r2430812613), [ex2](https://github.com/sarj-ai/bulbul/pull/1149#discussion_r2302749747))
28. **Infra**: terraform `local-exec` ban ([ex](https://github.com/sarj-ai/noura-iac/pull/85#discussion_r2623956724)); KSA region allowlist (me-central2) with comment suppression ([ex](https://github.com/sarj-ai/ai/pull/16#discussion_r2433828201)); hardcoded `'en'` locale defaults ([ex](https://github.com/sarj-ai/bulbul/pull/581#discussion_r2118303380)).

### New packages & CI gates

29. **`sarj-detekt-rules` + `sarj-swiftlint-rules`** (~70 mobile) — port SARJ005 (sealed-class unions), SARJ006 (enum over stringly tags, 21), try-block-size (9), assert-never/`when`-else discipline (13), `NoHardWiredCollaborator` DI rule (12), `RedundantNameContext` (13), Compose/SwiftUI hardcoded-string localization (9), `RequireUseForCloseable` (4), `HoistFormatterAllocation` (6), `no_gcd_async_after` (5). ([ex1](https://github.com/sarj-ai/noura-fe/pull/7#discussion_r2103171427), [ex2](https://github.com/sarj-ai/noura-fe/pull/51#discussion_r2350153895))
30. **PR-size/layer-mix gate** (~30) — reusable GitHub Action: fail/warn when changed LOC > 800 (excl. lockfiles), or a migration is mixed with non-migration code, or ≥3 layers (db/python/typescript/iac) touched; `size-override` label escape hatch. Mechanizes his "split into staged no-op PRs" ask. ([ex1](https://github.com/sarj-ai/bulbul/pull/343#pullrequestreview-2757284974), [ex2](https://github.com/sarj-ai/bulbul/pull/2851#pullrequestreview-4276468893))
31. **AI-doc/stray-file pre-commit** (~15) — fail on `*.backup/*.bak/*.orig`; warn on new `*_GUIDE.md`/`*_PLAN.md`/`SETUP*.md` outside docs/. ([ex1](https://github.com/sarj-ai/bulbul/pull/1084#discussion_r2283532444), [ex2](https://github.com/sarj-ai/noura-fe/pull/30#discussion_r2246861523))
32. **EXPLAIN gate** — CI job: PRs adding/modifying SQL in stores must include EXPLAIN ANALYZE output in the body or a `-- seq-scan-ok:` comment (mechanizes the CLAUDE.md mandate; pairs with Tier 4 index judgment). ([ex](https://github.com/sarj-ai/bulbul/pull/465#discussion_r2072736653))

## Tier 4 — Not statically checkable

~600 merged occurrences need judgment. Encode as the auto-invoked review bot's prompt (claude-code-action, Tier 2 row 1).

### Review bot prompt checklist (ready to paste)

1. **YAGNI (~149):** For every new public method, model field, endpoint, enum member, config knob, factory, or ABC in this diff, find at least one caller/reader in the PR or repo. If none exists, request deletion — "it will live on in version control." Flag abstractions with exactly one implementation and one call site; flag anything justified by future need ("we might", "eventually"). Recommend composition over inheritance.
2. **Redundant comments (~190):** Flag comments/docstrings that restate the adjacent identifier or code, AI-narration comments ("Step 1:", "// Convert to dict"), section banners, leftover scaffolding/TODOs without tickets, and docstrings longer than the function body. Recommend deletion; comments must explain WHY, not WHAT.
3. **Justify every Optional (~76):** For each new `X | None` / `?:` / nullable column, ask: under what concrete circumstance is this None? If the author can't name one, require the non-nullable type. Prefer `list[X]` + default_factory over `list[X] | None`. Flag `hasattr`/3-arg `getattr`/defensive truthiness checks on typed objects — trust the type contract.
4. **Illegal states (~50 residual beyond SARJ005):** When related state lives in parallel optionals, bool+payload pairs, or multiple useStates whose validity is interdependent, propose the concrete Literal-tagged union and name the illegal state the current type admits.
5. **Layering (~54):** Route handlers must be thin (validate → call service → return). Stores touch only their own table. No provider-specific (Zoho/vendor) logic in generic modules. Next.js: raw fetch in actions/routes belongs in an `Http*Service` class behind an interface; business logic belongs in the Python backend. Frontend stays dumb: sorting/aggregation/truncation happens server-side or in SQL.
6. **ABC boundaries (~27):** Suggest an ABC + constructor injection when a class wraps an external provider (STT/TTS/LLM/storage) or has an obvious sibling implementation. Do NOT suggest ABCs for single-implementation internal logic (no speculative abstractions).
7. **SQL performance (~38):** For every new/changed query: name the index it uses (check DATABASE_SCHEMA.txt); request EXPLAIN ANALYZE for new WHERE/ORDER BY; flag JOINs, DISTINCT, unindexed ORDER BY created_at, and >2-CTE queries. For every CREATE INDEX: name the exact query it serves; flag single-column FK/boolean indexes and prefix-redundant indexes as speculative.
8. **Schema judgment (~25):** New columns default to NOT NULL — demand a reason for NULL. Business-key columns: ask whether UNIQUE should be scoped per-organization. 3+ rarely-queried scalar columns → suggest one JSONB settings column with a pydantic/zod schema.
9. **Naming (~48):** Flag method names repeating the class noun (`MerchantStore.list_merchants` → `list`), files not named for their main export, util/helpers grab-bags, vocabulary inconsistent with existing schema or industry terms; private methods go below the public methods that call them (step-down rule).
10. **Inline single-use helpers (~27):** Flag helpers/wrapper components used exactly once, under ~5 lines, that don't isolate a separate concern → inline at the call site. (Counterweight to extraction suggestions — don't suggest extracting once-used code.)
11. **PR process (~30):** If a PR adds both new abstractions and their call sites, propose a 2-PR staging where PR 1 is a complete no-op (migrations/types/interfaces). Flag mixed-in mechanical cleanups (type-ignore removals, renames) for extraction into a separate immediately-mergeable PR. If the PR claims a perf improvement, ask for before/after logs.
12. **Misc:** Flag new cron/scheduler jobs — ask why event-driven (Pub/Sub on the state change) doesn't work. Flag new >100-line generated-looking .md docs → delete. Flag log calls interpolating variables → loguru kwargs; suggest `logger.bind()` only for repeated context. Flag UI hand-rolled tailwind/raw elements where a shadcn primitive exists; question every useEffect/useMemo not synchronizing with an external system.

## Appendix: per-slice summaries

- **py-app-1..4 (~3,211 comments):** Terse, extremely consistent type-design coaching: pydantic everywhere (parse-don't-validate, biggest cluster), StrEnum/discriminated unions, match+assert_never, skinny try + bubble-up, YAGNI deletion (✂️), store-layer SQL discipline (upserts, indexes, no OFFSET), constructor DI, timedelta/walrus/kwonly idioms. ~⅓ disappears with strict-config rollout, ~⅓ is ~12 new SARJ/semgrep rules, ~⅓ is LLM judgment.
- **py-tests (47):** Test realness dominates — real Psql stores/emulators over mocks and hand-rolled fakes (mock half now covered by TID251; fake-when-real-impl-exists half is not), plus pytest idiom enforcement (yield-fixture teardown, parametrize with exact expectations, no sys.path hacks).
- **ts-frontend (714):** Server-first (RSC/server actions, ~50), strict typing (no any/casts, zod at every boundary, unions+assertNever), React minimalism (delete useCallback/useMemo/useEffect, hoist constants, useTransition), shadcn consistency, aggressive deletion. Much is nominally covered but the strict config isn't enabled where the comments occur.
- **ts-backend (511):** Six asks repeated verbatim ≈70% of volume: skinny/removed try-catch, zod-parse every boundary, no casts/any, camelCase transforms at the wire boundary, delete dead comments, Http*Service architecture. Mostly strict-config rollout + TS ports of SARJ001/002/005/006.
- **sql-infra-config (297):** A fixed DDL catechism (idempotent, TEXT+CHECK, no PG enums, no speculative indexes, JSONB `'{}'`, app-layer validation) — ~half mechanizable as ~10 sarj-sql-lint rules; plus dependency/Terraform/cron YAGNI needing LLM review.
- **mobile (244, noura-fe):** His Python/TS house style ported to Kotlin/Swift — enums over stringly tags, sealed-class unions, kotlinx.serialization, don't-swallow exceptions, DI behind interfaces, ✂️ comments. Zero existing standards coverage; needs detekt/SwiftLint configs + a small custom-rules package.
- **general-reviews (480):** Process signal: split PRs into staged no-ops, Linear-ticket titles, attach screenshots/looms, delete AI-generated docs and artifacts, bootstrap uv/ruff/CI on new repos, and manual @claude review summoning — all automatable as CI gates + an auto-invoked review bot.
