# Lint expansion proposal — July 2026

Status: IN REVIEW — items 1-5 approved interactively 2026-07-16 (item 4 with
narrowed scope); items 6-15 decided per evidence by agreement that the PR
review is the approval gate for the remainder.

Evidence base: dry-runs and pattern surveys across 8 active repos (bulbul, summer,
tahded, ai, noura-be, automations, portal, pericles) on 2026-07-16. Bulbul
`.claude/worktrees/*` duplicates excluded from all counts. FP gate: measured
false-positive rate <= 5% -> error; 5-20% -> warn; > 20% -> redesign or drop.

## Security

### 1. eslint-plugin-security, curated subset (config)
Enable in `eslint.strict.mjs`: `detect-eval-with-expression`,
`detect-child-process`, `detect-buffer-noassert`, `detect-pseudoRandomBytes`.
Keep OFF: `detect-object-injection` (353 hits org-wide in dry-run, near-all FPs
— bracket access on typed objects), `detect-non-literal-fs-filename` (14 hits,
mostly legitimate file tooling), and `detect-unsafe-regex` (17 hits via the
safe-regex heuristic; superseded by the more precise regexp-plugin rule in
item 2). The TS stack currently has zero security linting; Python already gets
the ruff S-family via `select = ["ALL"]`.
- Evidence (dry-run, 2026-07-16, bulbul/summer/tahded/automations/pericles;
  portal run OOMed, rerun scoped pending): curated four rules fired ZERO times
  org-wide — pure guardrail, zero migration cost.
- Severity: error (curated set), off (FP-heavy set)
- Migration cost: new devDep for consumers; zero existing violations
- Decision: APPROVED (user, 2026-07-16)

### 2. eslint-plugin-regexp recommended (config)
ReDoS protection (`no-super-linear-backtracking`) plus regex correctness.
Largely autofixable.
- Evidence (same dry-run): no-super-linear-backtracking 3 hits, all real
  polynomial backtracking on user-influenced input (Slack text in
  automations/sales-requests-bot handler.ts:2060 and widget-state.ts:51;
  transcript text in pericles transcript-display.tsx:28). Correctness rules:
  no-obscure-range 6, no-dupe-characters-character-class 2 (bulbul).
- Severity: error
- Migration cost: 3 regex fixes + a handful of autofixes
- Decision: APPROVED (user, 2026-07-16)

### 3. Secrets-scanning standard: gitleaks config shipped via sync CLI (new sync target)
6 of 8 surveyed repos have no secret scanning (only bulbul and noura-be run
gitleaks). Ship `configs/gitleaks.toml` (extends default rules + org allowlist)
plus a documented pre-commit/lefthook snippet through `sarj-lint-configs sync`.
- Evidence (gitleaks 8.30.1 working-tree scan, 2026-07-16): 1,572 non-vendored
  findings org-wide; the vast majority are untracked local files (.env.local,
  playwright caches, .wrangler build artifacts) that pre-commit would never
  see. In git-TRACKED files: ~20 findings, mostly FPs (advisory-lock key
  constants, Clerk publishable keys, CF Access AUD tags) BUT including one
  confirmed committed credential: a SIP trunk auth_password in
  bulbul/python/bulbul/livekit/moataz-inbound-trunk.json, plus one
  build-arg in ai/python/api/cloudbuild.yaml:32 needing review. Rotate and
  remove both regardless of this proposal.
- Org allowlist needs: NEXT_PUBLIC_* keys, *_AUD tags, *_LOCK_KEY constants,
  .secrets.baseline, google-services.json (Android client keys are
  restricted-by-design), test fixture paths.
- Severity: pre-commit hook + CI step (blocking)
- Migration cost: one hook entry per repo
- Decision: APPROVED (user, 2026-07-16)

### 4. New Python rule SARJ022 `no-disabled-tls-verify` (new custom rule)
Flag `verify=False` / `ssl_verify=False` in HTTP client construction or calls
(httpx, requests, aiohttp) outside tests. Found live in production banking
adapters: `noura-be/python/common/adapters/vision_bank/v2/http_client.py:1205`
and `noura-be/digital-bank/banking-ai/common/adapters/banking/v2/http_client.py:897`.
Disabled certificate verification defeats TLS entirely (MITM).
- Evidence: 2 confirmed production hits motivated the rule (noura-be), but both
  use a custom-wrapper ssl_verify kwarg that the user-narrowed scope excludes.
  Implemented-rule dry-run across 5 Python repos (2,253 files): 0 findings,
  0 FPs — pure guardrail going forward.
- Severity: error
- Migration cost: zero (guardrail); the 2 noura-be wrapper sites still need
  manual remediation (consumer follow-ups)
- Decision: APPROVED WITH MODIFICATION (user, 2026-07-16): narrowed to httpx/requests verify=False only; custom-wrapper kwargs like ssl_verify are out of scope. The two noura-be sites therefore need manual remediation, tracked in consumer follow-ups.
- Note: added to shortlist during evidence gathering; ranked here because the
  hits are in payment-adjacent code.

### 5. New Python rule SARJ023 `httpx-timeout-required` (new custom rule)
Require explicit `timeout=` on `httpx.Client(...)` / `httpx.AsyncClient(...)`
construction and one-shot `httpx.get/post/...` calls. Honest framing: httpx has
a 5s default timeout (unlike requests), so this is not a hang-forever bug class;
it is an explicit-policy rule — the 5s default is routinely wrong in both
directions for LLM/voice workloads (spurious timeouts) and for webhook fan-out
(too slow). Ruff S113 only covers `requests`.
- Evidence: constructor sites lacking timeout (AST-verified sample):
  bulbul 26 grep-flagged of which sampled multi-line sites show ~half are FPs
  (timeout passed on a later line — the AST rule handles this correctly);
  confirmed TPs include `bulbul/python/agent/agent/lk/scenarios/custom.py:93`,
  `bulbul/python/sdk/src/sarj_platform_sdk/sdk.py:121`; noura-be 13 flagged;
  ai 2/2; summer 6/6 one-shot calls.
- Implemented-rule dry-run (AST-accurate, 2,253 files): bulbul 26, noura-be 26,
  summer 6, ai 1, tahded 0 — 59 sites total.
- Severity: warn initially (policy rule, not a bug class)
- Migration cost: 59 sites org-wide; trivial fix per site
- Decision: APPROVED (user, 2026-07-16)

### 6. New Python rule SARJ024 `no-credentialed-wildcard-cors` (new custom rule)
Flag `CORSMiddleware(allow_origins=["*"], ...)` when `allow_credentials=True`,
and wildcard fallbacks in conditional expressions
(`... if cors_enforce else ["*"]` — live at
`bulbul/python/webserver/webserver/create_app.py:797`).
- Implemented-rule dry-run: 4 hits, 4 confirmed true positives, 0 FPs:
  two credentialed wildcard-FALLBACK sites in bulbul (create_app.py:797 and a
  previously unknown one, public_api/app.py:310) and two wildcard+
  allow_credentials=True sites in ai dockerized model servers
  (stt-parakeet main.py:96, kokoro-tts api.py:350 — the credentials flag was
  confirmed present, contrary to the initial grep survey).
- Severity: error (measured FP rate 0%)
- Migration cost: 4 sites need fix or noqa
- Decision: APPROVED (maintainer judgment; PR review is the gate)

### 7. New Py+TS rule `no-unverified-jwt-decode` (SARJ025 + @sarj twin) (new custom rules)
Python: `jwt.decode(..., options={"verify_signature": False})`. TS:
`jsonwebtoken.decode()` / `jose.decodeJwt()` results used for authorization
decisions. Survey found ZERO live occurrences in main trees (the one
`verify_aud: False` hit is in a test). This is a preventive guardrail, not a
cleanup — proposing warn tier or drop.
- Evidence: 0 production hits
- Severity: warn (preventive) or drop
- Decision: DROPPED: zero live occurrences; custom-rule maintenance cost not justified today. Revisit if JWT surfaces grow.

### 8. New TS rule `@sarj/no-host-interpolated-fetch` (new custom rule)
SSRF/URL-injection: flag `fetch`/axios where template interpolation appears in
the origin position (scheme..first slash) and the value is not a recognized
env/config constant. 25 dynamic-URL call sites surveyed; origin-position
restriction is the FP control.
- Implemented-rule dry-run (3,222 files across 5 TS repos, 1 parse error):
  first iteration fired 3 times, all FPs (env-config host:
  c.env.POSTHOG_API_HOST in automations posthog proxy). Rule refined twice:
  (1) exempt origin-position member expressions on env/config/settings object
  chains; (2) apply the plain-identifier name allowlist (base/url/origin/host/
  endpoint/api prefixes-or-suffixes) symmetrically in origin position.
  Request-derived members (req.query.host, params.host) stay flagged; the
  known false negative (a trusted-looking local fed from user input) is
  documented in the rule. Post-refinement: 0 findings org-wide — guardrail.
- Severity: warn until real-world TP/FP data accumulates
- Decision: APPROVED at warn (maintainer judgment; FP rate to be measured and recorded before any escalation to error)

### 9. no-restricted-syntax additions (config)
`dangerouslySetInnerHTML` outside `components/ui/**` (survey: hits are shadcn
`chart.tsx` [exempt], `portal` mermaid-diagram renderer, `summer` file-upload
components — a handful of noqa-or-fix sites); `child_process.execSync` with
non-literal argument; `Buffer.allocUnsafe`.
- Evidence: dangerouslySetInnerHTML: 3 non-exempt files org-wide
- Severity: error (with components/ui exemption block, mirroring forbid-elements)
- Decision: APPROVED (maintainer judgment)

### 10. New TS rule `@sarj/no-timing-unsafe-compare` (new custom rule)
Port of Python SARJ011: `===`/`!==` where an operand identifier looks like a
token/signature/secret -> `crypto.timingSafeEqual`. Survey greps found zero
current hits; parity + preventive value only.
- Evidence: 0 current hits
- Severity: warn (preventive) or drop
- Decision: DROPPED: zero current hits; Python-side SARJ011 already guards the sensitive comparisons that exist. Revisit with evidence.

## Ergonomics

### 11. Ship .editorconfig via sync CLI (new sync target)
`.editorconfig` exists at standards root but is not distributed. Add a
CONFIG_NAMES entry so `sarj-lint-configs sync` writes it.
- Severity: n/a (distribution fix)
- Decision: APPROVED (maintainer judgment)

### 12. Ruff config: docstring-code-format + runtime-evaluated-base-classes (config)
`[format] docstring-code-format = true`; `[lint.flake8-type-checking]
runtime-evaluated-base-classes = ["pydantic.BaseModel",
"pydantic_settings.BaseSettings"]`. The latter eliminates a whole class of
TC001/TC002 false positives for every Pydantic consumer (all org Python repos).
- Severity: config change, autofix-safe
- Decision: APPROVED (maintainer judgment)

### 13. Replace deprecated no-return-await with @typescript-eslint/return-await "always" (config)
The current strict config enables core `no-return-await`, deprecated since
ESLint 8.46 and actively harmful in try/catch (drops the async frame from stack
traces). `return-await: ["error", "always"]` is the modern inverse and
autofixable. This fixes a defect in the existing config.
- Severity: error (replacement)
- Decision: APPROVED (maintainer judgment; fixes a defect in the current config)

## Quality

### 14. New TS rule `@sarj/require-error-cause` (new custom rule)
`throw new Error(...)` inside a catch block where the caught error is neither
referenced in the message nor passed as `{ cause }`. Parity with Python B904
(already enforced). Crude survey counts (all throw-new-Error without `cause`,
not yet catch-scoped): bulbul 54, summer 36, automations 71, portal 93,
pericles 42 — catch-scoped subset to be measured by the implemented rule.
- Implemented-rule dry-run (3,222 files): 0 catch-scoped violations org-wide —
  the crude grep counts were throws outside catch blocks. The rule is a
  B904-parity guardrail, not a cleanup.
- Severity: warn (guardrail; escalate alongside B904 conventions later)
- Decision: APPROVED at warn (maintainer judgment)

### 15. Autofixable unicorn additions (config)
`unicorn/prefer-at`, `unicorn/prefer-array-flat-map`,
`unicorn/explicit-length-check`. All autofixable; zero migration pain.
- Severity: error
- Decision: APPROVED (maintainer judgment)

## Considered and dropped

- Python `no-secret-in-url` (secrets interpolated into URL query strings):
  zero hits across 4 Python repos; SARJ012 no-secret-in-log already covers the
  adjacent risk. Not worth a rule today.
- Ruff S311 escalation: all 10 org hits are timing-jitter/backchannel
  randomness (legitimate non-crypto use). Rule already on via select=ALL;
  hits belong in per-site noqa, no config change.

## Adoption gaps appendix (not lint rules — org follow-ups)

- summer: no CI at all (empty .github/workflows); pyright installed but
  unconfigured; still on black while the org standard is ruff format.
- tahded: no Python type checker, no lint CI (Claude bots only), mixed
  eslint 8/9 across packages.
- Secret scanning absent: summer, tahded, portal, pericles, automations, ai
  (ai has bandit+pip-audit but no gitleaks).
- standards configs consumed by only 4 of 8 repos (bulbul deep; noura-be,
  portal, automations partial; summer/tahded/ai/pericles none).
- sarj-eslint repo checkout (v1.0.1) trails the published @sarj/eslint-plugin
  2.2.0 that consumers pin — the standards repo `packages/typescript` is the
  source of truth; consider archiving sarj-ai/sarj-eslint to remove confusion.

## Consumer follow-ups after release

- bulbul: bump `sarj-python-lint==0.8.0` pin in `.pre-commit-config.yaml` and
  add new `--rule` ids; bump `@sarj/eslint-plugin` to 2.3.0.
- automations: bump `@sarj/eslint-plugin` to 2.3.0.
- Repos without standards adoption: separate onboarding effort (see appendix).
