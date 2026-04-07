"""Slash command registry for MohaMind CLI."""

from dataclasses import dataclass, field
from typing import Awaitable, Callable


@dataclass
class Command:
    name: str
    description: str
    usage: str = ""
    handler: Callable[..., Awaitable[str | None]] | None = None
    aliases: list[str] = field(default_factory=list)


class CommandRegistry:
    def __init__(self):
        self._commands: dict[str, Command] = {}

    def register(self, cmd: Command) -> None:
        self._commands[cmd.name] = cmd
        for alias in cmd.aliases:
            self._commands[alias] = cmd

    def get(self, name: str) -> Command | None:
        return self._commands.get(name)

    def all_commands(self) -> list[Command]:
        seen = set()
        commands = []
        for cmd in self._commands.values():
            if cmd.name not in seen:
                seen.add(cmd.name)
                commands.append(cmd)
        return sorted(commands, key=lambda c: c.name)

    def get_completions(self) -> list[str]:
        seen = set()
        names = []
        for cmd in self._commands.values():
            if cmd.name not in seen:
                seen.add(cmd.name)
                names.append(f"/{cmd.name}")
        return sorted(names)

    def get_help_list(self) -> list[dict]:
        return [{"name": f"/{c.name}", "description": c.description} for c in self.all_commands()]
