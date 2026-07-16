# sarj-lint-configs

Ships the maximally-strict ruff / pyright / ESLint configs — plus the org gitleaks and editorconfig baselines — from `sarj-ai/standards` as a pip-installable package.

```bash
uv add --dev sarj-lint-configs
uv run sarj-lint-configs sync --only ruff          # writes .ruff-strict.toml
uv run sarj-lint-configs sync --only pyright       # writes .pyright-strict.json
uv run sarj-lint-configs sync --only eslint        # writes eslint.strict.mjs
uv run sarj-lint-configs sync --only gitleaks      # writes .gitleaks.toml
uv run sarj-lint-configs sync --only editorconfig  # writes .editorconfig
```

Then reference the synced file:

```toml
# pyproject.toml
[tool.ruff]
extend = ".ruff-strict.toml"
```

```json
// pyrightconfig.json
{ "extends": ".pyright-strict.json" }
```

```js
// eslint.config.mjs
import strict from "./eslint.strict.mjs";
export default [...strict];
```

`eslint.strict.mjs` peer requirements — install alongside `@sarj/eslint-plugin` (>= 2.3.0):

```bash
pnpm add -D eslint-plugin-security eslint-plugin-regexp
```

`.gitleaks.toml` extends the gitleaks default ruleset with the org allowlist (tuned on the 2026-07 eight-repo scan; evidence and per-rule decisions in sarj-ai/standards#89). Wire it as a pre-commit/lefthook hook plus a blocking CI step:

```yaml
# .pre-commit-config.yaml
- repo: https://github.com/gitleaks/gitleaks
  rev: v8.30.1
  hooks: [{id: gitleaks}]
```

Re-run sync with `--force` after upgrading. Programmatic access via `from sarj_lint_configs import RUFF_STRICT, PYRIGHT_STRICT, ESLINT_STRICT, GITLEAKS, EDITORCONFIG` (returns `pathlib.Path` into the wheel).
