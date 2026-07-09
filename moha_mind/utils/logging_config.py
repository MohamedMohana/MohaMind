"""Structured logging for MohaMind.

At import time the logger gets a console handler so early messages are
never lost. Entry points then call configure_logging() to pick a mode:

    cli    -> file only; the terminal belongs to the interactive UI
    daemon -> console + file; systemd/docker still capture stdout
    quiet  -> file only; one-shot mode where stdout is the answer

The file lives at ~/.mohamind/logs/mohamind.log (rotated, 5 MB x 3) and
timestamps are in the agent's timezone (TIMEZONE, default Asia/Riyadh),
matching what the CLI and scheduler display.
"""

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from moha_mind.config import settings

LOG_DIR = Path.home() / ".mohamind" / "logs"
LOG_FILE = LOG_DIR / "mohamind.log"

_MAX_BYTES = 5_000_000
_BACKUP_COUNT = 3


class TimezoneFormatter(logging.Formatter):
    """Stamp records in the agent's timezone, not the host's (VPS = UTC)."""

    def __init__(self, fmt: str | None = None, datefmt: str | None = None):
        super().__init__(fmt, datefmt)
        try:
            from zoneinfo import ZoneInfo

            self._tz = ZoneInfo(settings.timezone)
        except Exception:
            self._tz = None

    def formatTime(self, record, datefmt=None):  # noqa: N802 (stdlib API)
        dt = datetime.fromtimestamp(record.created, tz=self._tz)
        return dt.strftime(datefmt or "%Y-%m-%d %H:%M:%S %z")


def _console_handler() -> logging.Handler:
    try:
        from rich.console import Console
        from rich.logging import RichHandler

        handler = RichHandler(
            rich_tracebacks=True,
            show_path=False,
            markup=True,
            console=Console(stderr=True),
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
    except Exception:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(TimezoneFormatter("[%(asctime)s] %(levelname)-8s %(message)s"))
    return handler


def _file_handler(log_file: Path) -> logging.Handler:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_file,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(TimezoneFormatter("[%(asctime)s] %(levelname)-8s %(message)s"))
    return handler


def setup_logging() -> logging.Logger:
    """Initial logger with a console handler; reconfigured later by mode."""
    logger = logging.getLogger("mohamind")
    if logger.handlers:
        return logger
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    logger.addHandler(_console_handler())
    return logger


def configure_logging(mode: str = "daemon", log_file: Path | None = None) -> logging.Logger:
    """Swap the logger's handlers to match the run mode (see module docstring)."""
    logger = logging.getLogger("mohamind")
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    file_ok = True
    try:
        logger.addHandler(_file_handler(log_file or LOG_FILE))
    except Exception:
        file_ok = False

    # Daemons log to the console for systemd/docker; CLI and one-shot modes
    # keep the terminal clean — unless the log file is unusable, in which
    # case the console is better than losing logs entirely.
    if mode == "daemon" or not file_ok:
        logger.addHandler(_console_handler())

    return logger


log = setup_logging()
