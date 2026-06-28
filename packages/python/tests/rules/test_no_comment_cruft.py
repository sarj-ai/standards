from pathlib import Path

from sarj_python_lint.rules.no_comment_cruft import NoCommentCruft


def _check(source: str) -> list:
    return NoCommentCruft().check(Path("<t>.py"), source)


def test_flags_commented_out_statement():
    src = """
def f():
    x = compute()
    # return x + 1
    return x
"""
    diags = _check(src)
    assert len(diags) == 1
    assert "Commented-out code" in diags[0].message


def test_flags_commented_out_block_header():
    src = """
# for row in rows:
value = 1
"""
    assert len(_check(src)) == 1


def test_flags_commented_out_import():
    src = "# import os\nx = 1\n"
    assert len(_check(src)) == 1


def test_flags_section_banner():
    src = """
x = 1
# ============================
y = 2
"""
    assert len(_check(src)) == 1


def test_flags_region_marker():
    src = """
x = 1
# region helpers
y = 2
# endregion
"""
    assert len(_check(src)) == 2


def test_flags_leading_file_header_preamble():
    src = """# This module does a thing.
# It was written a while ago.
# Please be careful editing it.
# Contact the team before changes.
import os
"""
    diags = _check(src)
    assert len(diags) == 1
    assert "preamble" in diags[0].message


def test_allows_license_header_preamble():
    src = """# Copyright 2023 LiveKit, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# See the License for the specific language governing permissions.
import os
"""
    assert _check(src) == []


def test_allows_short_leading_comment():
    src = """# why this exists
import os
"""
    assert _check(src) == []


def test_allows_assert_raise_prose():
    src = """
def f():
    # assert this is true before we proceed
    # raise the question with the team first
    return go()
"""
    assert _check(src) == []


def test_flags_commented_out_assert_with_signal():
    src = """
def f():
    # assert result == expected
    return f()
"""
    assert len(_check(src)) == 1


def test_allows_prose_why_comment():
    src = """
def f():
    # retry because the upstream API is flaky under load
    return retry()
"""
    assert _check(src) == []


def test_allows_directive_comments():
    src = """
import os  # noqa: F401
x = eval("1")  # noqa: S307
y: int = 1  # type: ignore[assignment]
# sarj-noqa: SARJ001 — intentional
# TODO@nmaswood: revisit
"""
    assert _check(src) == []


def test_allows_trailing_explanatory_comment():
    src = "x = compute()  # returns cached value when warm\n"
    assert _check(src) == []


def test_does_not_flag_midfile_comment_run_as_preamble():
    src = """import os

x = 1
# alpha note
# beta note
# gamma note
# delta note
y = 2
"""
    assert _check(src) == []


def test_handles_unparseable_source():
    assert _check("def (:\n") == []
