"""Task Management MCP Server - manages tasks, reminders, and to-dos."""

import re
from typing import Optional

from moha_mind.agent.memory import MemoryManager


class TaskServer:
    """MCP server for task management operations."""

    def __init__(self, memory: MemoryManager):
        self.memory = memory

    async def handle_tool(self, tool_name: str, arguments: dict) -> str:
        handlers = {
            "add_task": self._add_task,
            "complete_task": self._complete_task,
            "list_tasks": self._list_tasks,
            "update_task": self._update_task,
            "set_reminder": self._set_reminder,
        }
        handler = handlers.get(tool_name)
        if handler:
            return await handler(**arguments)
        return f"Unknown tool: {tool_name}"

    async def _add_task(self, text: str, priority: str = "medium", due: Optional[str] = None) -> str:
        self.memory.add_task(text, priority, due)
        return f"Task added: {text} [{priority.upper()}]" + (f" due:{due}" if due else "")

    async def _complete_task(self, task_text: str) -> str:
        success = self.memory.complete_task(task_text)
        if success:
            return f"Task completed: {task_text}"
        return f"Task not found: {task_text}"

    async def _list_tasks(self, include_completed: bool = False) -> str:
        tasks = self.memory.get_task_section()
        if not tasks:
            return "No tasks found"
        active = [t for t in tasks if not t["done"]]
        completed = [t for t in tasks if t["done"]]

        lines = ["📋 Active Tasks:"]
        for i, t in enumerate(active, 1):
            due_info = f" (due {t['due']})" if t["due"] else ""
            lines.append(f"  {i}. [{t['priority'].upper()}] {t['text']}{due_info}")

        if include_completed and completed:
            lines.append("\n✅ Completed:")
            for t in completed:
                lines.append(f"  - {t['text']}")

        return "\n".join(lines)

    async def _update_task(
        self, task_text: str, new_text: Optional[str] = None, priority: Optional[str] = None, due: Optional[str] = None
    ) -> str:
        content = self.memory.read("tasks")
        lines = content.split("\n")
        updated = False
        for i, line in enumerate(lines):
            if task_text.lower() in line.lower() and "- [ ]" in line:
                if new_text:
                    lines[i] = line.replace(task_text, new_text)
                if priority:
                    lines[i] = re.sub(r"\[(HIGH|MED|LOW)\]", f"[{priority.upper()}]", lines[i])
                if due:
                    lines[i] = re.sub(r"due:\d{4}-\d{2}-\d{2}", f"due:{due}", lines[i])
                    if "due:" not in lines[i]:
                        lines[i] = f"{lines[i].rstrip()} due:{due}"
                updated = True
                break
        if updated:
            self.memory.write("tasks", "\n".join(lines))
            return f"Task updated: {task_text}"
        return f"Task not found: {task_text}"

    async def _set_reminder(self, task_text: str, remind_date: str) -> str:
        content = self.memory.read("tasks")
        if task_text.lower() in content.lower():
            return f"Reminder set for {task_text} on {remind_date}"
        return f"Task not found: {task_text}"
