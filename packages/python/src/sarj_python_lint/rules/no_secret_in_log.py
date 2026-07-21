"""SARJ012: detect secrets passed by keyword argument to a logging call.

Logging a secret value (token, password, api key, jwt, credential, etc.) by
keyword argument leaks it into log sinks — files, stdout, log aggregators —
where it persists far beyond its intended lifetime and is readable by anyone
with log access. Prefer redaction (`token_prefix=token[:6]`) or omission.

We are deliberately precise: only the keyword-argument form
(`logger.info("x", token=token)`) is flagged. F-strings are too noisy to detect
reliably, so they're out of scope.

References:
- https://owasp.org/www-community/vulnerabilities/Information_exposure_through_log_files
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING, override

from sarj_python_lint._secret_names import _tokens, is_secret_name
from sarj_python_lint.rule_base import Diagnostic, Rule, parse_or_none
from sarj_python_lint.rules._logging import is_logger_expr


if TYPE_CHECKING:
    from pathlib import Path


# Logging method names (the `.attr` of the call's func).
_LOG_METHODS = frozenset({"debug", "info", "warning", "warn", "error", "exception", "critical"})

# A redaction marker (`token_prefix`, `password_hash`, `secret_masked`,
# `api_key_tag`) means the keyword carries a masked/derived value, not the raw
# secret — the intended safe form.
_REDACTION_RE = re.compile(
    r"prefix|suffix|redact|mask|hash|hint|_len|length",
    re.IGNORECASE,
)

# `tag` marks a redaction tag derived purely for logging
# (`api_key_tag=_api_key_log_tag(api_key)`), but only as a WHOLE token — matched
# as a substring it wrongly exempts raw env secrets like `staging_secret`
# (`s·tag·ing`), which is a leak.
_WHOLE_TOKEN_REDACTION_MARKERS = frozenset({"tag"})


def _is_secret_keyword(name: str) -> bool:
    """True if the keyword name names a raw secret (not a redacted derivative)."""
    if _REDACTION_RE.search(name):
        return False
    if any(tok in _WHOLE_TOKEN_REDACTION_MARKERS for tok in _tokens(name)):
        return False
    return is_secret_name(name)


class NoSecretInLog(Rule):
    """Secret passed by keyword argument to a logging call."""

    id: str = "no-secret-in-log"
    code: str = "SARJ012"
    description: str = "Secret passed by keyword to a logging call — redact or omit."

    @override
    def check(self, path: Path, source: str) -> list[Diagnostic]:
        tree = parse_or_none(path, source)
        if tree is None:
            return []
        diags: list[Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not _is_logging_call(node):
                continue
            for kw in node.keywords:
                # `**kwargs` has arg=None — nothing to inspect.
                if kw.arg is None:
                    continue
                if _is_secret_keyword(kw.arg):
                    diags.append(
                        Diagnostic(
                            path=path,
                            line=getattr(kw.value, "lineno", node.lineno),
                            col=getattr(kw.value, "col_offset", node.col_offset) + 1,
                            code=self.code,
                            message=(
                                f"Secret keyword `{kw.arg}` passed to a logging "
                                "call leaks it to log sinks — redact "
                                "(e.g. `token_prefix=token[:6]`) or omit it."
                            ),
                        )
                    )
        return diags


def _is_logging_call(node: ast.Call) -> bool:
    """Return True if `node` looks like `logger.<level>(...)`.

    Precise on the method name (must be a known log level) and conservative on
    the object: the shared resolver walks the receiver chain so factory/builder
    forms (`logging.getLogger(__name__).info`, `logger.bind(...).info`) are
    recognised, not just `logger` / `self.logger`.
    """
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr not in _LOG_METHODS:
        return False
    return is_logger_expr(func.value)
