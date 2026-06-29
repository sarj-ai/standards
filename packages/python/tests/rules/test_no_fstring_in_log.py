from pathlib import Path
from typing import TYPE_CHECKING

from sarj_python_lint.rules.no_fstring_in_log import NoFstringInLog


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic


def _check(source: str) -> list[Diagnostic]:
    return NoFstringInLog().check(Path("<t>.py"), source)


def test_flags_fstring_in_logger_info():
    src = 'logger.info(f"call {call_id} done")\n'
    diags = _check(src)
    assert len(diags) == 1
    assert "keyword arguments" in diags[0].message


def test_flags_fstring_with_loguru_alias():
    src = 'log.warning(f"slow: {elapsed}s")\n'
    assert len(_check(src)) == 1


def test_flags_module_logging_attr_receiver():
    src = 'self.logger.error(f"failed {err}")\n'
    assert len(_check(src)) == 1


def test_flags_chained_bind_receiver():
    src = 'logger.bind(call_id=cid).info(f"done {x}")\n'
    assert len(_check(src)) == 1


def test_flags_getlogger_chain():
    src = 'logging.getLogger(__name__).warning(f"slow {dt}")\n'
    assert len(_check(src)) == 1


def test_flags_opt_chain():
    src = 'logger.opt(lazy=True).debug(f"v={value}")\n'
    assert len(_check(src)) == 1


def test_allows_structured_kwargs():
    src = 'logger.info("call done", call_id=call_id)\n'
    assert _check(src) == []


def test_allows_plain_string_literal():
    src = 'logger.info("nothing interpolated")\n'
    assert _check(src) == []


def test_allows_fstring_without_interpolation():
    src = 'logger.info(f"constant text")\n'
    assert _check(src) == []


def test_ignores_non_logger_receiver():
    src = 'response.info(f"{x}")\n'
    assert _check(src) == []


def test_ignores_non_log_method():
    src = 'logger.bind(context=f"{x}")\n'
    assert _check(src) == []
