"""Interactive input handler using prompt_toolkit.

Provides autocomplete for slash commands, history persistence,
and a styled prompt that adapts to the user's mood.
"""

from pathlib import Path

from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.shortcuts import PromptSession

from moha_mind.cli.themes import get_theme

HISTORY_DIR = Path.home() / ".mohamind"
HISTORY_FILE = HISTORY_DIR / "history"


class SlashCompleter(Completer):
    def __init__(self, commands: list[str]):
        self.commands = commands

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith("/"):
            word = text.lstrip("/")
            for cmd in self.commands:
                cmd_name = cmd.lstrip("/")
                if cmd_name.startswith(word) and cmd_name != word:
                    yield Completion(
                        cmd,
                        start_position=-len(text),
                        display=cmd,
                        display_meta="",
                    )


class InputHandler:
    def __init__(self, commands: list[str] | None = None):
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)

        self.completer = SlashCompleter(commands or [])
        self.session: PromptSession | None = None
        self._session_signature: str | None = None

    def _get_session(self, mood: str = "neutral") -> PromptSession:
        theme = get_theme(mood)
        signature = f"{theme['accent']}:{theme.get('prompt_label', 'mohamind')}"

        if self.session is None or self._session_signature != signature:
            from prompt_toolkit.styles import Style as PTStyle

            style = PTStyle.from_dict(
                {
                    "prompt": f"bold {theme['accent']}",
                    "": f"{theme['primary']}",
                }
            )

            self.session = PromptSession(
                history=FileHistory(str(HISTORY_FILE)),
                auto_suggest=AutoSuggestFromHistory(),
                completer=self.completer,
                style=style,
                multiline=False,
                enable_open_in_editor=True,
            )
            self._session_signature = signature
        return self.session

    async def get_input(self, mood: str = "neutral") -> str:
        session = self._get_session(mood)
        prompt_label = get_theme(mood).get("prompt_label", "mohamind")
        try:
            result = await session.prompt_async(
                message=[("class:prompt", f"{prompt_label} ❯ ")],
            )
            return result.strip()
        except (EOFError, KeyboardInterrupt):
            return "/quit"

    def get_input_sync(self, mood: str = "neutral") -> str:
        session = self._get_session(mood)
        prompt_label = get_theme(mood).get("prompt_label", "mohamind")
        try:
            result = session.prompt(
                message=[("class:prompt", f"{prompt_label} ❯ ")],
            )
            return result.strip()
        except (EOFError, KeyboardInterrupt):
            return "/quit"
