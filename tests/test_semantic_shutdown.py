import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from moha_mind.config import Settings

SHUTDOWN_SCRIPT = dedent(r"""
    import os
    import sys
    import threading
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    from moha_mind import main
    from moha_mind.agent import core
    from moha_mind.agent.memory import MemoryManager
    from moha_mind.config import Settings
    from moha_mind.utils.logging_config import log

    name, phase = sys.argv[1:]
    log.disabled = True
    core.settings = Settings(_env_file=None, llm_strategy="solo", memory_router_enabled=False,
                             agent_tool_timeout_seconds=0.2)
    core.AsyncOpenAI = MagicMock()

    class Embedder:
        provider = "test"
        model = "test"
        dim = 2
        block = False

        def encode(self, texts):
            current_phase = "query" if texts == ["dentist"] else "sync"
            if self.block and current_phase == phase:
                print("EMBEDDING_BLOCKED", flush=True)
                threading.Event().wait()
            return [[1.0, 0.0] for _ in texts]

    embedder = Embedder()
    core.build_embedder = lambda: embedder
    memory = MemoryManager(memory_dir="memory")
    memory.write("tasks", "# Tasks\n- schedule dentist appointment\n")
    agent = core.MohaMindAgent(memory)
    agent.semantic_index.sync()
    path = memory.memory_path / "tasks.md"
    old_mtime = path.stat().st_mtime
    memory.write("tasks", "# Tasks\n- schedule dentist appointment tomorrow\n")
    os.utime(path, (old_mtime + 10, old_mtime + 10))
    embedder.block = True
    agent._route_memory_context = MagicMock(return_value=([], {}))
    agent._build_recall_context = MagicMock(return_value="")
    call = SimpleNamespace(id="search-1", function=SimpleNamespace(name=name, arguments='{"query":"dentist"}'))
    message = MagicMock(content=None, tool_calls=[call])
    message.model_dump.return_value = {
        "role": "assistant", "content": None,
        "tool_calls": [{"id": call.id, "type": "function",
                        "function": {"name": name, "arguments": call.function.arguments}}],
    }

    async def completion(**kwargs):
        results = [item for item in kwargs["messages"] if item["role"] == "tool"]
        if results:
            assert "timed out" in results[-1]["content"], results[-1]
            reply = SimpleNamespace(content="SEARCH_TIMED_OUT", tool_calls=None)
        else:
            reply = message
        return SimpleNamespace(choices=[SimpleNamespace(message=reply)])

    agent._chat_completion_with_fallback = completion
    main.bootstrap = AsyncMock(return_value=(memory, agent, None, None))
    main._has_api_key = lambda: True
    main.configure_logging = MagicMock()
    sys.argv = ["mohamind", "-p", "find my dentist appointment"]
    main.run()
    print("CLI_EXITED", flush=True)
""")


@pytest.mark.parametrize("name", ["search_memory", "semantic_search_memory"])
@pytest.mark.parametrize("phase", ["sync", "query"])
def test_one_shot_exits_with_permanently_blocked_embedding(tmp_path, name, phase):
    environment = {key: value for key, value in os.environ.items() if key.lower() not in Settings.model_fields}
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    result = subprocess.run(
        [sys.executable, "-u", "-c", SHUTDOWN_SCRIPT, name, phase],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=8,
    )

    assert result.returncode == 0, result.stderr
    assert "EMBEDDING_BLOCKED" in result.stdout
    assert "SEARCH_TIMED_OUT" in result.stdout
    assert "CLI_EXITED" in result.stdout
    assert result.stderr == ""
    assert (tmp_path / "memory/tasks.md").read_text() == "# Tasks\n- schedule dentist appointment tomorrow\n"
    with sqlite3.connect(tmp_path / "memory/.semantic.db") as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        expected = "schedule dentist appointment" + (" tomorrow" if phase == "query" else "")
        assert connection.execute("SELECT text FROM chunks").fetchall() == [(expected,)]
