from __future__ import annotations

from sarj_python_lint.rule_base import Rule
from sarj_python_lint.rules.inefficient_string_concat_in_loop import (
    InefficientStringConcatInLoop,
)
from sarj_python_lint.rules.no_fat_try_blocks import NoFatTryBlocks
from sarj_python_lint.rules.no_sequential_await import NoSequentialAwait
from sarj_python_lint.rules.prefer_discriminated_union import PreferDiscriminatedUnion
from sarj_python_lint.rules.prefer_str_enum import PreferStrEnum


REGISTRY: dict[str, type[Rule]] = {
    NoSequentialAwait.id: NoSequentialAwait,
    InefficientStringConcatInLoop.id: InefficientStringConcatInLoop,
    PreferDiscriminatedUnion.id: PreferDiscriminatedUnion,
    PreferStrEnum.id: PreferStrEnum,
    NoFatTryBlocks.id: NoFatTryBlocks,
}

__all__ = ["REGISTRY"]
