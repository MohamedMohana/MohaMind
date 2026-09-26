import asyncio
import contextlib
import hashlib
import json
import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from rich.console import Console

from moha_mind.config import settings
from moha_mind.utils.logging_config import log

BRIDGE_SOURCE = Path(__file__).parent / "bridge"


class IncomingMessage(BaseModel):
    type: Literal["message"]
    id: str = Field(min_length=1, max_length=256)
    text: str = Field(min_length=1, max_length=8000)
    from_me: Literal[True]
    is_self: Literal[True]


def _claim_message(path: Path, account: str, message_id: str) -> bool:
    digest = hashlib.sha256(f"{account}:{message_id}".encode()).hexdigest()
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS received (id TEXT PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
        cursor = connection.execute("INSERT OR IGNORE INTO received (id) VALUES (?)", (digest,))
        return cursor.rowcount == 1


async def prepare_bridge(session_dir: Path, *, install: bool = False) -> Path:
    if not shutil.which(settings.whatsapp_node_path):
        raise RuntimeError("WhatsApp requires Node.js 20 or newer. Install Node.js, then run whatsapp setup.")
    version = await asyncio.create_subprocess_exec(
        settings.whatsapp_node_path,
        "--version",
        stdout=asyncio.subprocess.PIPE,
    )
    stdout, _ = await version.communicate()
    if version.returncode or int(stdout.decode().strip().lstrip("v").split(".")[0]) < 20:
        raise RuntimeError("WhatsApp requires Node.js 20 or newer.")
    runtime = session_dir / "bridge"
    await asyncio.to_thread(runtime.mkdir, parents=True, exist_ok=True, mode=0o700)
    expected = await asyncio.to_thread((BRIDGE_SOURCE / "package-lock.json").read_bytes)
    marker = runtime / ".installed"
    digest = hashlib.sha256(expected).hexdigest()
    installed = marker.exists() and marker.read_text() == digest and (runtime / "node_modules" / "baileys").is_dir()
    for name in ("bridge.mjs", "policy.mjs", "package.json", "package-lock.json"):
        await asyncio.to_thread(shutil.copyfile, BRIDGE_SOURCE / name, runtime / name)
    if not installed:
        if not install:
            raise RuntimeError("WhatsApp dependencies are not installed. Run: uv run mohamind whatsapp setup")
        npm = shutil.which("npm")
        if not npm:
            raise RuntimeError("WhatsApp setup requires npm, included with Node.js.")
        Console().print("Installing the optional WhatsApp bridge dependencies…")
        process = await asyncio.create_subprocess_exec(npm, "ci", "--omit=dev", "--no-fund", "--no-audit", cwd=runtime)
        try:
            if await process.wait():
                raise RuntimeError("WhatsApp dependency installation failed. Check npm output and retry setup.")
        except BaseException:
            if process.returncode is None:
                process.terminate()
                await process.wait()
            raise
        await asyncio.to_thread(marker.write_text, digest)
    return runtime / "bridge.mjs"


class WhatsAppBridge:
    def __init__(self, session_dir: Path, console: Console | None = None):
        self.session_dir = session_dir
        self.console = console or Console()
        self.ready = asyncio.Event()
        self.messages: asyncio.Queue[IncomingMessage] = asyncio.Queue(maxsize=32)
        self.account = ""
        self.process: asyncio.subprocess.Process | None = None
        self.reader: asyncio.Task | None = None
        self.pending: dict[str, asyncio.Future] = {}
        self._write_lock = asyncio.Lock()

    async def start(self, *, pair: bool = False) -> None:
        script = await prepare_bridge(self.session_dir, install=pair)
        auth_dir = self.session_dir / "auth"
        await asyncio.to_thread(auth_dir.mkdir, parents=True, exist_ok=True, mode=0o700)
        args = [settings.whatsapp_node_path, str(script), str(auth_dir)]
        if pair:
            args.append("--pair")
        self.process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            limit=256 * 1024,
        )
        self.reader = asyncio.create_task(self._read_events())

    async def _read_events(self) -> None:
        try:
            while line := await self.process.stdout.readline():
                try:
                    event = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if not isinstance(event, dict):
                    continue
                kind = event.get("type")
                if kind == "qr":
                    self.console.print("On your phone: WhatsApp → Settings → Linked Devices → Link a Device.")
                    self.console.print(str(event.get("terminal", "")), markup=False, highlight=False)
                elif kind == "connected":
                    self.account = str(event.get("account", ""))
                    self.ready.set()
                    self.console.print("WhatsApp linked. Only your Message Yourself chat is connected to MohaMind.")
                elif kind == "disconnected":
                    self.ready.clear()
                    self.console.print("WhatsApp disconnected; reconnecting…")
                elif kind in {"sent", "send_error"}:
                    future = self.pending.get(event.get("request_id"))
                    if future and not future.done():
                        if kind == "sent":
                            future.set_result(None)
                        else:
                            future.set_exception(
                                RuntimeError("WhatsApp could not confirm delivery; retry was not attempted.")
                            )
                elif kind == "message":
                    try:
                        message = IncomingMessage.model_validate(event)
                        self.messages.put_nowait(message)
                    except (ValidationError, asyncio.QueueFull):
                        log.warning("WhatsApp message rejected: invalid input or queue full")
                elif kind == "too_long":
                    self.console.print("A WhatsApp message was too long. Keep messages under 8,000 characters.")
                elif kind == "fatal":
                    raise RuntimeError(str(event.get("reason", "WhatsApp bridge failed.")))
            code = await self.process.wait()
            if code:
                raise RuntimeError("WhatsApp bridge stopped unexpectedly. Run whatsapp setup to check the connection.")
        finally:
            self.ready.clear()
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(RuntimeError("WhatsApp connection closed; delivery outcome is unknown."))

    async def wait_ready(self) -> None:
        waiter = asyncio.create_task(self.ready.wait())
        try:
            done, _ = await asyncio.wait([waiter, self.reader], return_when=asyncio.FIRST_COMPLETED, timeout=180)
            if self.reader in done:
                await self.reader
                if not self.account:
                    raise RuntimeError("WhatsApp closed before linking.")
            elif waiter not in done:
                raise RuntimeError("WhatsApp connection timed out. Retry: uv run mohamind whatsapp setup")
        finally:
            waiter.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await waiter

    async def send_message(self, text: str, chat_id: str | None = None) -> None:
        if chat_id is not None:
            raise ValueError("WhatsApp messages can only go to the linked account's self-chat.")
        if not self.ready.is_set():
            raise RuntimeError("WhatsApp is not connected.")
        async with self._write_lock:
            for start in range(0, len(text), 3500):
                request_id = uuid.uuid4().hex
                future = asyncio.get_running_loop().create_future()
                self.pending[request_id] = future
                payload = json.dumps({"type": "send", "request_id": request_id, "text": text[start : start + 3500]})
                try:
                    self.process.stdin.write((payload + "\n").encode())
                    await self.process.stdin.drain()
                    await asyncio.wait_for(future, timeout=60)
                finally:
                    self.pending.pop(request_id, None)
                    if not future.done():
                        future.cancel()

    async def close(self) -> None:
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except TimeoutError:
                self.process.kill()
                await self.process.wait()
        if self.reader:
            self.reader.cancel()
            with contextlib.suppress(asyncio.CancelledError, RuntimeError):
                await self.reader


class WhatsAppBot:
    def __init__(self, agent, bridge: WhatsAppBridge):
        self.agent = agent
        self.bridge = bridge

    async def handle_message(self, message: IncomingMessage) -> None:
        claimed = await asyncio.to_thread(
            _claim_message,
            self.bridge.session_dir / "received.sqlite3",
            self.bridge.account,
            message.id,
        )
        if not claimed:
            return
        text = message.text.strip()
        if text == "/help":
            response = (
                "Message yourself to talk to MohaMind using your existing memory. "
                "Ask to save a task, list reminders, or recall a fact. Text messages only. "
                "Scheduled notifications require: uv run mohamind whatsapp --schedule"
            )
        else:
            account_id = hashlib.sha256(self.bridge.account.encode()).hexdigest()[:16]
            response = await self.agent.chat(text, chat_id=f"whatsapp:{account_id}")
        await self.bridge.send_message(response)

    async def consume(self) -> None:
        while True:
            message = await self.bridge.messages.get()
            try:
                await self.handle_message(message)
            except Exception:
                log.error("WhatsApp request failed; it will not be replayed automatically")
                with contextlib.suppress(Exception):
                    await self.bridge.send_message(
                        "I couldn't finish this request. Check the current state before retrying an action."
                    )
            finally:
                self.bridge.messages.task_done()


async def run_whatsapp(*, pair: bool = False, schedule: bool = False) -> None:
    bridge = WhatsAppBridge(Path(settings.whatsapp_session_dir).resolve())
    agent = None
    worker = None
    scheduler = None
    try:
        await bridge.start(pair=pair)
        await bridge.wait_ready()
        if pair:
            await bridge.reader
            bridge.console.print("Session saved. Start chat with: uv run mohamind whatsapp")
            return
        from moha_mind.main import bootstrap

        memory, agent, _, _ = await bootstrap(require_telegram=False)
        bot = WhatsAppBot(agent, bridge)
        worker = asyncio.create_task(bot.consume())
        if schedule:
            from moha_mind.scheduler.jobs import SchedulerJobs

            scheduler = SchedulerJobs(agent, memory, bridge)
            scheduler.start()
        bridge.console.print("Send /help in Message Yourself. Press Ctrl+C here to stop.")
        await bridge.reader
    finally:
        if scheduler:
            scheduler.stop()
        if worker:
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker
        await bridge.close()
        if agent and agent.external_mcp:
            await agent.external_mcp.aclose()
