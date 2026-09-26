import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Update
from telegram.error import BadRequest, Conflict, NetworkError
from telegram.ext import Updater

from moha_mind.config import settings
from moha_mind.telegram_bot.bot import MohaMindBot
from moha_mind.utils.logging_config import configure_logging


@pytest.fixture
def bot(tmp_memory):
    return MohaMindBot(MagicMock(), tmp_memory)


@pytest.mark.parametrize("error", [NetworkError("httpx.ReadError: "), NetworkError("Bad Gateway")])
def test_polling_network_errors_are_concise_warnings(bot, caplog, error):
    with caplog.at_level(logging.WARNING, logger="mohamind"):
        bot._polling_error(error)

    record = caplog.records[-1]
    assert record.levelno == logging.WARNING
    assert "Retrying automatically" in record.getMessage()
    assert record.exc_info is None


@pytest.mark.parametrize("error", [Conflict("another getUpdates request"), BadRequest("invalid request")])
def test_polling_configuration_errors_remain_errors(bot, caplog, error):
    with caplog.at_level(logging.WARNING, logger="mohamind"):
        bot._polling_error(error)

    record = caplog.records[-1]
    assert record.levelno == logging.ERROR
    assert "Retrying automatically" not in record.getMessage()


def test_polling_errors_respect_cli_file_logging(bot, tmp_path, capsys):
    from moha_mind.utils.logging_config import setup_logging

    log_file = tmp_path / "mohamind.log"
    logger = configure_logging("cli", log_file=log_file)
    try:
        bot._polling_error(NetworkError("httpx.ReadError: "))

        assert "Retrying automatically" in log_file.read_text()
        assert not capsys.readouterr().err
    finally:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()
        setup_logging()


async def test_polling_recovers_after_read_and_gateway_errors(bot, caplog):
    update = Update(update_id=123)
    responses = iter([NetworkError("httpx.ReadError: "), NetworkError("Bad Gateway"), [update]])

    async def get_updates(**kwargs):
        if not kwargs["timeout"]:
            return []
        response = next(responses, None)
        if isinstance(response, Exception):
            raise response
        if response is not None:
            return response
        await asyncio.Event().wait()

    telegram_bot = MagicMock()
    telegram_bot.initialize = AsyncMock()
    telegram_bot.shutdown = AsyncMock()
    telegram_bot.delete_webhook = AsyncMock(side_effect=[NetworkError("Bad Gateway"), True])
    telegram_bot.get_updates = AsyncMock(side_effect=get_updates)
    updater = Updater(telegram_bot, asyncio.Queue())
    bot.app = MagicMock()
    bot.app.initialize = AsyncMock(side_effect=updater.initialize)
    bot.app.start = AsyncMock()
    bot.app.stop = AsyncMock()
    bot.app.shutdown = AsyncMock(side_effect=updater.shutdown)
    bot.app.updater = updater

    try:
        with caplog.at_level(logging.WARNING):
            await bot.start()
            received = await asyncio.wait_for(updater.update_queue.get(), timeout=10)

        assert received is update
        assert updater.running
        assert telegram_bot.delete_webhook.await_count == 2
        warnings = [record for record in caplog.records if "Retrying automatically" in record.getMessage()]
        assert len(warnings) == 2
        assert all(record.exc_info is None for record in warnings)
        assert not any("Exception happened while polling" in record.getMessage() for record in caplog.records)
    finally:
        await bot.stop()


async def test_shutdown_after_polling_startup_failure(bot):
    bot.app = MagicMock()
    bot.app.updater.running = False
    bot.app.updater.stop = AsyncMock()
    bot.app.running = True
    bot.app.stop = AsyncMock()
    bot.app.shutdown = AsyncMock()

    await bot.stop()

    bot.app.updater.stop.assert_not_awaited()
    bot.app.stop.assert_awaited_once()
    bot.app.shutdown.assert_awaited_once()


async def test_setup_gives_long_polling_network_headroom(bot, monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "123456:dummy-token")
    app = bot.setup()
    try:
        assert app.bot._request[0].read_timeout == 15
        assert app.bot.request.read_timeout == 20
    finally:
        await app.bot._request[0].shutdown()
        await app.bot.request.shutdown()
