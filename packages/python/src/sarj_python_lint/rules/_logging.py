"""Shared logging-receiver detection for SARJ012/SARJ017.

A single resolver for "does this receiver expression evaluate to a logger?",
used by both the secret-in-log and f-string-in-log rules so they recognise the
same factory/builder forms.
"""

from __future__ import annotations

import ast


_LOGGER_NAMES = frozenset({"logger", "log", "logging", "loguru", "_logger", "_log"})

_LOGGER_FACTORIES = frozenset({"getlogger", "getchild"})


def is_logger_expr(expr: ast.expr) -> bool:
    """True if `expr` evaluates to a logger.

    Resolves the whole receiver chain so adapter/builder/factory calls are
    caught: `logger.bind(...).info(...)`, `logger.opt(lazy=True).debug(...)`,
    `logging.getLogger(__name__).info(...)`, `self.logger.error(...)`.
    """
    if isinstance(expr, ast.Name):
        return expr.id.lower() in _LOGGER_NAMES
    if isinstance(expr, ast.Attribute):
        if expr.attr.lower() in _LOGGER_NAMES or expr.attr.lower() in _LOGGER_FACTORIES:
            return True
        return is_logger_expr(expr.value)
    if isinstance(expr, ast.Call):
        if isinstance(expr.func, ast.Attribute) and expr.func.attr.lower() in _LOGGER_FACTORIES:
            return True
        return is_logger_expr(expr.func)
    return False
