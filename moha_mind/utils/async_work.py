import asyncio
import contextvars
import threading
from concurrent.futures import Future
from typing import Any, Callable


def start_daemon_worker(handler: Callable[..., Any], *args: Any) -> asyncio.Future:
    loop = asyncio.get_running_loop()
    context = contextvars.copy_context()
    result: Future = Future()

    def run() -> None:
        if not result.set_running_or_notify_cancel():
            return
        try:
            value = context.run(handler, *args)
        except BaseException as exc:
            result.set_exception(exc)
        else:
            result.set_result(value)

    thread = threading.Thread(target=run, name="mohamind-memory-search", daemon=True)
    thread.start()
    return asyncio.wrap_future(result, loop=loop)
