"""Structured logging for MohaMind."""

import logging
import sys

from moha_mind.config import settings


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("mohamind")

    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    try:
        from rich.console import Console
        from rich.logging import RichHandler

        console = Console(stderr=True)
        handler = RichHandler(
            rich_tracebacks=True,
            show_path=False,
            markup=True,
            console=console,
        )
    except Exception:
        handler = logging.StreamHandler(sys.stderr)

    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

    return logger


log = setup_logging()
