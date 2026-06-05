# sarj-lint-configs

Ships the maximally-strict ruff / pyright / ESLint configs from `sarj-ai/standards` as a pip-installable package.

```bash
uv add --dev sarj-lint-configs
uv run sarj-lint-configs sync --only ruff      # writes .ruff-strict.toml
uv run sarj-lint-configs sync --only pyright   # writes .pyright-strict.toml
uv run sarj-lint-configs sync --only eslint    # writes eslint.strict.mjs
```

Then reference the synced file:

```toml
# pyproject.toml
[tool.ruff]
extend = ".ruff-strict.toml"
```

```json
// pyrightconfig.json
{ "extends": ".pyright-strict.toml" }
```

```js
// eslint.config.mjs
import strict from "./eslint.strict.mjs";
export default [...strict];
```

Re-run sync with `--force` after upgrading. Programmatic access via `from sarj_lint_configs import RUFF_STRICT, PYRIGHT_STRICT, ESLINT_STRICT` (returns `pathlib.Path` into the wheel).
