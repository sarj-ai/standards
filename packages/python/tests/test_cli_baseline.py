from __future__ import annotations

import json
from pathlib import Path

from sarj_python_lint.__main__ import main

# An existing rule with a deterministic, repeatable diagnostic message.
RULE = "no-secret-in-log"
ONE = 'logger.info("event", password=pw)\n'
TWO = 'logger.info("a", password=pw)\nlogger.warning("b", password=pw2)\n'
ONE_PLUS_NEW = 'logger.info("a", password=pw)\nlogger.error("b", token=tok)\n'


def _write(p: Path, body: str) -> Path:
    p.write_text(body, encoding="utf-8")
    return p


def test_plain_check_fails_on_violation(tmp_path: Path) -> None:
    f = _write(tmp_path / "a.py", ONE)
    assert main(["check", "--rule", RULE, str(f)]) == 1


def test_exit_zero_reports_but_passes(tmp_path: Path) -> None:
    f = _write(tmp_path / "a.py", ONE)
    assert main(["check", "--rule", RULE, "--exit-zero", str(f)]) == 0


def test_write_baseline_then_suppressed(tmp_path: Path) -> None:
    f = _write(tmp_path / "a.py", ONE)
    bl = tmp_path / "baseline.json"
    assert main(["check", "--rule", RULE, "--write-baseline", str(bl), str(f)]) == 0
    assert len(json.loads(bl.read_text())) == 1
    assert main(["check", "--rule", RULE, "--baseline", str(bl), str(f)]) == 0


def test_baseline_catches_new_distinct_violation(tmp_path: Path) -> None:
    f = _write(tmp_path / "a.py", ONE)
    bl = tmp_path / "baseline.json"
    main(["check", "--rule", RULE, "--write-baseline", str(bl), str(f)])
    _write(tmp_path / "a.py", ONE_PLUS_NEW)  # adds a distinct `token=` violation
    assert main(["check", "--rule", RULE, "--baseline", str(bl), str(f)]) == 1


def test_baseline_count_catches_extra_identical_violation(tmp_path: Path) -> None:
    # Two identical messages: baseline records count=1, the 2nd occurrence fails.
    f = _write(tmp_path / "a.py", ONE)
    bl = tmp_path / "baseline.json"
    main(["check", "--rule", RULE, "--write-baseline", str(bl), str(f)])
    _write(tmp_path / "a.py", TWO)
    assert main(["check", "--rule", RULE, "--baseline", str(bl), str(f)]) == 1
