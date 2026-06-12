from __future__ import annotations

from sarj_python_lint.rule_base import Rule
from sarj_python_lint.rules.inefficient_string_concat_in_loop import (
    InefficientStringConcatInLoop,
)
from sarj_python_lint.rules.no_secret_in_log import NoSecretInLog
from sarj_python_lint.rules.no_sentinel_return_on_except import NoSentinelReturnOnExcept
from sarj_python_lint.rules.no_sequential_await import NoSequentialAwait
from sarj_python_lint.rules.no_unreachable_after_terminal import (
    NoUnreachableAfterTerminal,
)
from sarj_python_lint.rules.prefer_constant_time_secret_compare import (
    PreferConstantTimeSecretCompare,
)
from sarj_python_lint.rules.prefer_discriminated_union import PreferDiscriminatedUnion
from sarj_python_lint.rules.prefer_str_enum import PreferStrEnum
from sarj_python_lint.rules.try_block_too_large import TryBlockTooLarge


REGISTRY: dict[str, type[Rule]] = {
    NoSequentialAwait.id: NoSequentialAwait,
    InefficientStringConcatInLoop.id: InefficientStringConcatInLoop,
    PreferDiscriminatedUnion.id: PreferDiscriminatedUnion,
    PreferStrEnum.id: PreferStrEnum,
    NoSentinelReturnOnExcept.id: NoSentinelReturnOnExcept,
    NoUnreachableAfterTerminal.id: NoUnreachableAfterTerminal,
    TryBlockTooLarge.id: TryBlockTooLarge,
    PreferConstantTimeSecretCompare.id: PreferConstantTimeSecretCompare,
    NoSecretInLog.id: NoSecretInLog,
}

__all__ = ["REGISTRY"]
