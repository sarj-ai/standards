from __future__ import annotations

from typing import TYPE_CHECKING

from sarj_sql_lint.rules.insert_requires_on_conflict import InsertRequiresOnConflict
from sarj_sql_lint.rules.no_limit_offset import NoLimitOffset
from sarj_sql_lint.rules.no_pg_enum import NoPgEnum
from sarj_sql_lint.rules.prefer_jsonb import PreferJsonb


if TYPE_CHECKING:
    from sarj_sql_lint.rule_base import Rule


REGISTRY: dict[str, type[Rule]] = {
    NoPgEnum.id: NoPgEnum,
    InsertRequiresOnConflict.id: InsertRequiresOnConflict,
    PreferJsonb.id: PreferJsonb,
    NoLimitOffset.id: NoLimitOffset,
}

__all__ = ["REGISTRY"]
