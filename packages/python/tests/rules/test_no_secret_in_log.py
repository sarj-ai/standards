from pathlib import Path
from typing import TYPE_CHECKING

from sarj_python_lint.rules.no_secret_in_log import NoSecretInLog


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic


def _check(source: str) -> list[Diagnostic]:
    return NoSecretInLog().check(Path("<test>.py"), source)


def test_flags_token_keyword():
    src = """
logger.info("auth", token=token)
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ012"


def test_flags_api_key_keyword_on_error():
    src = """
log.error("x", api_key=k)
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ012"


def test_flags_each_secret_keyword():
    src = """
logger.warning("auth", token=token, password=pw)
"""
    assert len(_check(src)) == 2


def test_flags_apikey_without_underscore():
    src = """
logger.debug("x", apikey=k)
"""
    assert len(_check(src)) == 1


def test_flags_case_insensitive_keyword():
    src = """
logger.critical("x", AuthToken=t)
"""
    assert len(_check(src)) == 1


def test_flags_self_logger():
    src = """
self.logger.info("auth", secret=s)
"""
    assert len(_check(src)) == 1


def test_flags_logging_module_call():
    src = """
logging.error("boom", credential=c)
"""
    assert len(_check(src)) == 1


def test_flags_getlogger_factory_receiver():
    """`logging.getLogger(__name__).info(...)` is now recognised (SARJ017 parity)."""
    src = """
logging.getLogger(__name__).info("auth", token=token)
"""
    assert len(_check(src)) == 1


def test_flags_bind_builder_receiver():
    """`logger.bind(...).info(...)` adapter chain resolves to a logger."""
    src = """
logger.bind(request_id=rid).warning("auth", password=pw)
"""
    assert len(_check(src)) == 1


def test_flags_module_logger_attribute_chain():
    src = """
app.logging.getLogger("svc").error("x", secret=s)
"""
    assert len(_check(src)) == 1


def test_allows_token_prefix():
    """A redacted prefix name doesn't match the secret pattern."""
    src = """
logger.info("auth", token_prefix=token[:6])
"""
    assert _check(src) == []


def test_allows_no_keywords():
    src = """
logger.info("ok")
"""
    assert _check(src) == []


def test_allows_non_secret_keyword():
    src = """
logger.info("done", user_id=uid, count=n)
"""
    assert _check(src) == []


def test_skips_non_logger_object():
    """`foo.info(...)` isn't a logger — object name doesn't look like one."""
    src = """
foo.info("x", token=t)
"""
    assert _check(src) == []


def test_skips_non_log_method():
    """`logger.send(...)` isn't a log-level method."""
    src = """
logger.send("x", token=t)
"""
    assert _check(src) == []


def test_skips_double_star_kwargs():
    src = """
logger.info("x", **secrets)
"""
    assert _check(src) == []


def test_handles_syntax_error():
    src = "def broken(:\n"
    assert _check(src) == []


def test_diagnostic_points_at_value():
    src = """
logger.info("auth", token=token)
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].line == 2
