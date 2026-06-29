from __future__ import annotations

from sarj_iac_lint.rule_base import Rule
from sarj_iac_lint.rules.no_comment_cruft import NoCommentCruft
from sarj_iac_lint.rules.no_hardcoded_private_cidr import NoHardcodedPrivateCidr
from sarj_iac_lint.rules.require_deletion_protection import RequireDeletionProtection


REGISTRY: dict[str, type[Rule]] = {
    RequireDeletionProtection.id: RequireDeletionProtection,
    NoCommentCruft.id: NoCommentCruft,
    NoHardcodedPrivateCidr.id: NoHardcodedPrivateCidr,
}

__all__ = ["REGISTRY"]
