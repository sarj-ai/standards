from pathlib import Path

from sarj_python_lint.rules.no_secret_in_log import NoSecretInLog


def _check(source: str) -> list:
    return NoSecretInLog().check(Path("<test>.py"), source)


def test_flags_token_keyword():
    src = """
logger.info("auth", token=token)
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ011"


def test_flags_api_key_keyword_on_error():
    src = """
log.error("x", api_key=k)
"""
    diags = _check(src)
    assert len(diags) == 1
    assert diags[0].code == "SARJ011"


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
