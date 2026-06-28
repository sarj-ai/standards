from __future__ import annotations

from sarj_python_lint.rule_base import Rule
from sarj_python_lint.rules.inefficient_string_concat_in_loop import (
    InefficientStringConcatInLoop,
)
from sarj_python_lint.rules.no_comment_cruft import NoCommentCruft
from sarj_python_lint.rules.no_fat_try_blocks import NoFatTryBlocks
from sarj_python_lint.rules.no_fstring_in_log import NoFstringInLog
from sarj_python_lint.rules.no_isinstance_union_chain import NoIsinstanceUnionChain
from sarj_python_lint.rules.no_secret_in_log import NoSecretInLog
from sarj_python_lint.rules.no_sentinel_return_on_except import NoSentinelReturnOnExcept
from sarj_python_lint.rules.no_sequential_await import NoSequentialAwait
from sarj_python_lint.rules.no_unreachable_after_terminal import (
    NoUnreachableAfterTerminal,
)
from sarj_python_lint.rules.prefer_class_row import PreferClassRow
from sarj_python_lint.rules.prefer_constant_time_secret_compare import (
    PreferConstantTimeSecretCompare,
)
from sarj_python_lint.rules.prefer_discriminated_union import PreferDiscriminatedUnion
from sarj_python_lint.rules.prefer_str_enum import PreferStrEnum
from sarj_python_lint.rules.prefer_struct_over_namedtuple import (
    PreferStructOverNamedtuple,
)
from sarj_python_lint.rules.prefer_timedelta_for_durations import (
    PreferTimedeltaForDurations,
)
from sarj_python_lint.rules.pydantic_at_boundaries import PydanticAtBoundaries


REGISTRY: dict[str, type[Rule]] = {
    NoSequentialAwait.id: NoSequentialAwait,
    InefficientStringConcatInLoop.id: InefficientStringConcatInLoop,
    PreferDiscriminatedUnion.id: PreferDiscriminatedUnion,
    PreferClassRow.id: PreferClassRow,
    PreferStrEnum.id: PreferStrEnum,
    NoFatTryBlocks.id: NoFatTryBlocks,
    NoIsinstanceUnionChain.id: NoIsinstanceUnionChain,
    PydanticAtBoundaries.id: PydanticAtBoundaries,
    NoSentinelReturnOnExcept.id: NoSentinelReturnOnExcept,
    NoUnreachableAfterTerminal.id: NoUnreachableAfterTerminal,
    PreferConstantTimeSecretCompare.id: PreferConstantTimeSecretCompare,
    NoSecretInLog.id: NoSecretInLog,
    PreferTimedeltaForDurations.id: PreferTimedeltaForDurations,
    PreferStructOverNamedtuple.id: PreferStructOverNamedtuple,
    NoCommentCruft.id: NoCommentCruft,
    NoFstringInLog.id: NoFstringInLog,
}

__all__ = ["REGISTRY"]
