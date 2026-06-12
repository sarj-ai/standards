"""SARJ011: detect secrets passed by keyword argument to a logging call.

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
from pathlib import Path

from sarj_python_lint.rule_base import Diagnostic, Rule

# Logging method names (the `.attr` of the call's func).
_LOG_METHODS = frozenset(
    {"debug", "info", "warning", "warn", "error", "exception", "critical"}
)

# Names that look like a logger object. We're permissive on the object but
# require it to plausibly be a logger to avoid flagging unrelated `.info(...)`
# calls.
_LOGGER_NAMES = frozenset({"logger", "log", "logging"})

# A keyword name leaks a secret if it CONTAINS a secret word (so `AuthToken`,
# `api_key`, `userPassword` all match) UNLESS it also carries a redaction marker
# (`token_prefix`, `password_hash`, `secret_masked`) — those are the intended
# safe forms, not the raw value.
_SECRET_WORD_RE = re.compile(
    r"token|secret|password|passwd|api_?key|jwt|credential|authorization",
    re.IGNORECASE,
)
_REDACTION_RE = re.compile(
    r"prefix|suffix|redact|mask|hash|hint|_len|length",
    re.IGNORECASE,
)


def _is_secret_keyword(name: str) -> bool:
    """True if the keyword name names a raw secret (not a redacted derivative)."""
    if _REDACTION_RE.search(name):
        return False
    return _SECRET_WORD_RE.search(name) is not None


class NoSecretInLog(Rule):
    """Secret passed by keyword argument to a logging call."""

    id = "no-secret-in-log"
    code = "SARJ011"
    description = "Secret passed by keyword to a logging call — redact or omit."

    def check(self, path: Path, source: str) -> list[Diagnostic]:
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
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
    the object: it must be a Name in {logger, log, logging} or an Attribute
    ending in one of those (e.g. `self.logger`, `self.log`).
    """
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr not in _LOG_METHODS:
        return False
    return _looks_like_logger(func.value)


def _looks_like_logger(value: ast.AST) -> bool:
    """Return True if `value` names a logger object (case-insensitively)."""
    if isinstance(value, ast.Name):
        return value.id.lower() in _LOGGER_NAMES
    if isinstance(value, ast.Attribute):
        # e.g. `self.logger`, `cls.log`
        return value.attr.lower() in _LOGGER_NAMES
    return False
