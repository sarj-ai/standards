from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from sarj_python_lint.rules.no_manual_log_prefix import NoManualLogPrefix


if TYPE_CHECKING:
    from sarj_python_lint.rule_base import Diagnostic


def _check(source: str) -> list[Diagnostic]:
    return NoManualLogPrefix().check(Path("<t>.py"), source)


_LOG_METHODS = (
    "debug",
    "info",
    "warning",
    "warn",
    "error",
    "exception",
    "critical",
    "fatal",
    "trace",
    "success",
)


@pytest.mark.parametrize("method", _LOG_METHODS)
def test_flags_manual_prefix_in_every_log_method(method: str):
    diags = _check(f'logger.{method}("[Comp] something happened")\n')
    assert len(diags) == 1
    assert diags[0].code == "SARJ029"
    assert "structured context" in diags[0].message


@pytest.mark.parametrize(
    "receiver",
    [
        "logger",
        "log",
        "logging",
        "loguru",
        "_logger",
        "_log",
        "LOGGER",
        "Logger",
    ],
)
def test_flags_every_bare_logger_name(receiver: str):
    assert len(_check(f'{receiver}.info("[X] msg")\n')) == 1


@pytest.mark.parametrize(
    "receiver",
    [
        "self.logger",
        "self._log",
        "cls.logger",
        "app.logging",
    ],
)
def test_flags_attribute_chain_ending_in_logger_name(receiver: str):
    assert len(_check(f'{receiver}.info("[X] msg")\n')) == 1


@pytest.mark.parametrize(
    "call",
    [
        'logger.bind(component="x").info("[X] msg")',
        'logger.opt(lazy=True).debug("[X] msg")',
        'logging.getLogger(__name__).warning("[X] msg")',
        'self.logger.bind(a=1).opt(lazy=True).info("[X] msg")',
        'structlog.get_logger().info("[X] msg")',
    ],
)
def test_flags_builder_and_factory_chains(call: str):
    assert len(_check(call + "\n")) == 1


def test_flags_log_with_level_as_first_arg_message_is_second():
    assert len(_check('logger.log(logging.INFO, "[X] msg")\n')) == 1


def test_ignores_log_with_single_positional_no_message_present():
    assert _check('logger.log("[X] msg")\n') == []


def test_flags_leading_literal_of_plus_concat():
    assert len(_check('logger.info("[X] " + detail)\n')) == 1


def test_flags_leading_literal_of_fstring():
    assert len(_check('logger.info(f"[X] {detail}")\n')) == 1


def test_flags_leading_literal_of_plus_concat_of_fstrings():
    assert len(_check('logger.info("[X] got " + f"{value}")\n')) == 1


def test_flags_prefix_with_space_and_multiword_component():
    assert len(_check('logger.info("[TTS Pronunciation] normalized")\n')) == 1


@pytest.mark.parametrize(
    "tag",
    [
        "[STT]",
        "[AgentDispatch]",
        "[AUDIO_GENERATOR]",
        "[WEBHOOK NOTIFIER]",
        "[my-component]",
    ],
)
def test_flags_real_corpus_style_tags(tag: str):
    assert len(_check(f'logger.info("{tag} ready")\n')) == 1


@pytest.mark.parametrize(
    "source",
    [
        'logger.info("plain message no bracket")\n',
        "logger.debug('another plain one')\n",
    ],
)
def test_allows_message_without_bracket(source: str):
    assert _check(source) == []


@pytest.mark.parametrize(
    "message",
    [
        "[Errno 2] no such file",
        "[1, 2] pair",
        "[1,2] pair",
        "[123] numeric",
        "[12:34] timestamp",
        "['a', 'b'] list repr",
        "[] empty",
        "[  ] spaces only",
        "[--] dashes only",
    ],
)
def test_does_not_fire_on_data_shaped_brackets(message: str):
    assert _check(f"logger.info({message!r})\n") == []


def test_does_not_fire_when_bracket_not_at_start():
    assert _check('logger.info("done [X]")\n') == []


def test_does_not_fire_on_leading_whitespace_before_bracket():
    assert _check('logger.info(" [X] msg")\n') == []


@pytest.mark.parametrize(
    "source",
    [
        'response.info("[X] msg")\n',
        'catalog.info("[X] msg")\n',
        'client.debug("[X] msg")\n',
        'self.metrics.error("[X] msg")\n',
    ],
)
def test_ignores_non_logger_receiver(source: str):
    assert _check(source) == []


@pytest.mark.parametrize(
    "source",
    [
        'print("[X] msg")\n',
        'raise ValueError("[X] bad")\n',
        'sys.stdout.write("[X] msg")\n',
    ],
)
def test_ignores_prefix_outside_any_logging_call(source: str):
    assert _check(source) == []


@pytest.mark.parametrize(
    "source",
    [
        'logger.bind(context="[X]")\n',
        'logger.new("[X] msg")\n',
        'logger.remove("[X] msg")\n',
    ],
)
def test_ignores_non_log_method(source: str):
    assert _check(source) == []


def test_ignores_prefix_passed_as_keyword_argument():
    assert _check('logger.info("msg", detail="[X] side")\n') == []


def test_ignores_fstring_starting_with_interpolation():
    assert _check('logger.info(f"{prefix} [X] rest")\n') == []


def test_ignores_logger_attribute_access_without_call():
    assert _check("handler = logger.info\n") == []


def test_empty_source_returns_no_diagnostics():
    assert _check("") == []


@pytest.mark.parametrize(
    "source",
    [
        "def (:\n",
        'logger.info("[X] msg"\n',
        "class:\n",
    ],
)
def test_syntax_error_returns_empty(source: str):
    assert _check(source) == []


def test_multiple_violations_returned_in_line_order():
    src = 'logger.info("[A] x")\nlogger.debug("[B] y")\nlogger.error("[C] z")\n'
    diags = _check(src)
    assert [d.line for d in diags] == [1, 2, 3]


def test_line_and_col_point_at_the_call_single_line():
    diags = _check('logger.info("[X] msg")\n')
    assert len(diags) == 1
    assert diags[0].line == 1
    assert diags[0].col == 1


def test_line_and_col_point_at_the_call_nonzero_column():
    diags = _check('if x: self.logger.info("[X] msg")\n')
    assert len(diags) == 1
    assert diags[0].line == 1
    assert diags[0].col == 7


def test_line_and_col_point_at_the_call_multiline():
    diags = _check('logger.info(\n    "[X] msg",\n)\n')
    assert len(diags) == 1
    assert diags[0].line == 1
    assert diags[0].col == 1


def test_flags_prefix_inside_comprehension():
    assert len(_check('[logger.info("[X] msg") for i in items]\n')) == 1
