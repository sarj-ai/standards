from __future__ import annotations

import json
from pathlib import Path

from sarj_python_lint.__main__ import main

RULE = "prefer-struct-over-namedtuple"


def _write(p: Path, body: str) -> Path:
    p.write_text(body, encoding="utf-8")
    return p


def test_plain_check_fails_on_violation(tmp_path: Path) -> None:
    f = _write(tmp_path / "a.py", "from collections import namedtuple\n")
    assert main(["check", "--rule", RULE, str(f)]) == 1


def test_exit_zero_reports_but_passes(tmp_path: Path) -> None:
    f = _write(tmp_path / "a.py", "from collections import namedtuple\n")
    assert main(["check", "--rule", RULE, "--exit-zero", str(f)]) == 0


def test_write_baseline_then_suppressed(tmp_path: Path) -> None:
    f = _write(tmp_path / "a.py", "from collections import namedtuple\n")
    bl = tmp_path / "baseline.json"
    assert main(["check", "--rule", RULE, "--write-baseline", str(bl), str(f)]) == 0
    assert len(json.loads(bl.read_text())) == 1
    # The existing violation is now baselined → clean.
    assert main(["check", "--rule", RULE, "--baseline", str(bl), str(f)]) == 0


def test_baseline_still_catches_new_violation(tmp_path: Path) -> None:
    f = _write(tmp_path / "a.py", "from collections import namedtuple\n")
    bl = tmp_path / "baseline.json"
    main(["check", "--rule", RULE, "--write-baseline", str(bl), str(f)])
    # Introduce a NEW, distinct violation (aliased import call).
    _write(
        tmp_path / "a.py",
        "from collections import namedtuple\nimport collections as c\nR = c.namedtuple('R', 'x')\n",
    )
    assert main(["check", "--rule", RULE, "--baseline", str(bl), str(f)]) == 1
