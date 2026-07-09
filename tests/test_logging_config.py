"""Tests for run-mode logging: file routing, console policy, timezone stamps."""

import logging
from logging.handlers import RotatingFileHandler

from moha_mind.utils.logging_config import TimezoneFormatter, configure_logging


def _handler_types(logger: logging.Logger) -> list[type]:
    return [type(h) for h in logger.handlers]


def _restore_default():
    """Put the logger back to its import-time console-only state."""
    logger = logging.getLogger("mohamind")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    from moha_mind.utils import logging_config

    logging_config.setup_logging()


class TestConfigureLogging:
    def test_cli_mode_is_file_only(self, tmp_path):
        logger = configure_logging("cli", log_file=tmp_path / "m.log")
        try:
            assert _handler_types(logger) == [RotatingFileHandler]
        finally:
            _restore_default()

    def test_quiet_mode_is_file_only(self, tmp_path):
        logger = configure_logging("quiet", log_file=tmp_path / "m.log")
        try:
            assert _handler_types(logger) == [RotatingFileHandler]
        finally:
            _restore_default()

    def test_daemon_mode_keeps_console(self, tmp_path):
        logger = configure_logging("daemon", log_file=tmp_path / "m.log")
        try:
            types = _handler_types(logger)
            assert RotatingFileHandler in types
            assert len(types) == 2  # file + console
        finally:
            _restore_default()

    def test_messages_reach_the_file(self, tmp_path):
        log_file = tmp_path / "m.log"
        logger = configure_logging("cli", log_file=log_file)
        try:
            logger.info("hello from the test")
            logger.handlers[0].flush()
            content = log_file.read_text(encoding="utf-8")
            assert "hello from the test" in content
            assert "INFO" in content
        finally:
            _restore_default()

    def test_reconfigure_does_not_stack_handlers(self, tmp_path):
        configure_logging("daemon", log_file=tmp_path / "m.log")
        logger = configure_logging("cli", log_file=tmp_path / "m.log")
        try:
            assert len(logger.handlers) == 1
        finally:
            _restore_default()

    def test_unwritable_file_falls_back_to_console(self, tmp_path):
        blocker = tmp_path / "not-a-dir"
        blocker.write_text("file, not a directory")
        logger = configure_logging("cli", log_file=blocker / "m.log")
        try:
            assert logger.handlers, "logs must not be silently dropped"
            assert RotatingFileHandler not in _handler_types(logger)
        finally:
            _restore_default()


class TestTimezoneFormatter:
    def test_timestamp_uses_configured_timezone(self):
        formatter = TimezoneFormatter("[%(asctime)s] %(message)s")
        record = logging.LogRecord("mohamind", logging.INFO, "", 0, "tick", None, None)
        stamp = formatter.formatTime(record)
        # Asia/Riyadh is UTC+3 year-round.
        assert stamp.endswith("+0300")
