import asyncio
import contextvars
import threading

import pytest

from moha_mind.utils.async_work import start_daemon_worker


async def test_worker_preserves_context_without_using_default_executor():
    context = contextvars.ContextVar("search_context", default="unset")
    context.set("request")
    caller = threading.get_ident()

    def search():
        return context.get(), threading.get_ident(), threading.current_thread().daemon

    value, worker, daemon = await start_daemon_worker(search)

    assert value == "request"
    assert worker != caller
    assert daemon


async def test_worker_error_reaches_caller():
    def search():
        raise ValueError("embedding failed")

    with pytest.raises(ValueError, match="embedding failed"):
        await start_daemon_worker(search)


@pytest.mark.parametrize("fail", [False, True])
def test_worker_can_finish_after_event_loop_closes(monkeypatch, fail):
    release = threading.Event()
    threads = []
    errors = []
    monkeypatch.setattr(threading, "excepthook", errors.append)

    async def run():
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(lambda _, error: errors.append(error))
        started = asyncio.Event()

        def search():
            threads.append(threading.current_thread())
            loop.call_soon_threadsafe(started.set)
            release.wait(timeout=2)
            if fail:
                raise ValueError("late embedding failure")
            return "late result"

        worker = start_daemon_worker(search)
        await asyncio.wait_for(started.wait(), timeout=1)
        assert not worker.done()

    try:
        asyncio.run(run())
        assert threads and threads[0].is_alive()
    finally:
        release.set()
        for thread in threads:
            thread.join(timeout=2)

    assert all(not thread.is_alive() for thread in threads)
    assert not errors
