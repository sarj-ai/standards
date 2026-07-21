"""Shared predicate for deciding whether an identifier names secret material.

Used by both SARJ011 (`prefer-constant-time-secret-compare`) and SARJ012
(`no-secret-in-log`) so the two rules never diverge on what counts as a secret.

The historical implementation matched a secret word as a bare *substring*, which
misfired on a large false-positive class observed in a real audit:

- LLM usage counters that merely embed `token`: `token_count`, `prompt_tokens`,
  `completion_tokens`, `total_tokens`, `max_tokens`, `n_tokens`, `num_tokens`,
  `tokenize`, `tokenizer`, `token_budget`.
- Row-id / handle names: `api_key_id`, `*_key_id` — the id of a key row, not the
  key material.
- Boolean feature / presence / state flags: `password_enabled`,
  `token_present`, `password_set`, `password_configured` — a boolean answering
  "is it there / was it set", not the credential itself. A `type` discriminator
  is the same: `token_type` is `"Bearer"`, `credential_type` is a class name.
- Innocent words embedding a secret word: `secretary` (embeds `secret`).

We fix this with two changes:

1. Match a secret word only as a WHOLE token (after snake_case / camelCase
   splitting), never a substring. This alone clears `tokenize`, `tokenizer`,
   `secretary`, and every *pluralized* `tokens` counter (plural `tokens` is not
   the singular secret word `token`).
2. Disqualify any identifier whose tokens include a counter / row-id / flag
   marker (`count`, `budget`, `id`, `enabled`, ...) even when a secret word is
   also present — this clears `token_count`, `api_key_id`, `password_enabled`.
"""

from __future__ import annotations

from itertools import pairwise
import re


_SECRET_WORDS = frozenset(
    {
        "token",
        "secret",
        "password",
        "passwd",
        "jwt",
        "credential",
        "credentials",
        "authorization",
        "signature",
        "hmac",
        "digest",
        "hash",
        "apikey",
    }
)

# Tokens that mark a counter, row-id, feature flag, or boolean presence/state
# marker. Their presence means the identifier is metadata *about* a secret, not
# the secret itself, so it is not a leak / timing surface even when a secret word
# is also present: `token_present`, `password_set`, and `password_configured` are
# booleans, not credentials.
_INNOCUOUS_WORDS = frozenset(
    {
        "count",
        "counts",
        "budget",
        "limit",
        "limits",
        "id",
        "ids",
        "enabled",
        "disabled",
        "flag",
        "flags",
        "present",
        "set",
        "unset",
        "configured",
        "missing",
        "required",
        "valid",
        "invalid",
        "exists",
        "type",
        "types",
    }
)

# camelCase / PascalCase / ALLCAPS / digit run splitter, applied to each
# snake/kebab segment. `APIKey` -> ["API", "Key"], `authToken` -> ["auth", "Token"].
_CAMEL_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
_SEGMENT_RE = re.compile(r"[^A-Za-z0-9]+")


def _tokens(identifier: str) -> list[str]:
    """Ordered lowercase tokens from snake_case + camelCase decomposition.

    Also yields each whole snake/kebab segment lowercased, so a pathological
    mixed-case single word like `ToKeN` (which camel-splitting shreds into
    `to`/`ke`/`n`) still surfaces its intended `token` form.
    """
    tokens: list[str] = []
    for segment in _SEGMENT_RE.split(identifier):
        if not segment:
            continue
        tokens.append(segment.lower())
        tokens.extend(part.lower() for part in _CAMEL_RE.findall(segment))
    return tokens


def is_secret_name(identifier: str) -> bool:
    """True if `identifier` names raw secret material (a credential, not metadata)."""
    tokens = _tokens(identifier)
    if any(tok in _INNOCUOUS_WORDS for tok in tokens):
        return False
    if any(tok in _SECRET_WORDS for tok in tokens):
        return True
    return _has_api_key(tokens)


def _has_api_key(tokens: list[str]) -> bool:
    """True if `api` is immediately followed by `key` (the split form of `api_key`)."""
    return any(a == "api" and b == "key" for a, b in pairwise(tokens))
