"""Memory Store MCP Server - manages persistent memory via MD files."""

from typing import Optional

from moha_mind.agent.memory import MemoryManager


class MemoryStoreServer:
    """MCP server for memory CRUD operations."""

    def __init__(self, memory: MemoryManager):
        self.memory = memory

    async def handle_tool(self, tool_name: str, arguments: dict) -> str:
        handlers = {
            "save_memory": self._save,
            "read_memory": self._read,
            "search_memory": self._search,
            "update_profile": self._update_profile,
            "get_profile": self._get_profile,
            "remember_fact": self._remember_fact,
            "recall_facts": self._recall_facts,
            "save_note": self._save_note,
            "read_note": self._read_note,
            "list_notes": self._list_notes,
            "append_to_section": self._append_to_section,
        }
        handler = handlers.get(tool_name)
        if handler:
            return await handler(**arguments)
        return f"Unknown tool: {tool_name}"

    async def _save(self, category: str, content: str) -> str:
        self.memory.save_entry(category, content)
        return f"Saved to {category}"

    async def _read(self, category: str) -> str:
        content = self.memory.read(category)
        return content if content else f"No data in {category}"

    async def _search(self, query: str, categories: Optional[list[str]] = None) -> str:
        results = self.memory.search(query, categories)
        if not results:
            return "No results found"
        return "\n".join(f"[{r['category']}:{r['line_number']}] {r['context']}" for r in results[:10])

    async def _update_profile(self, section: str, content: str) -> str:
        self.memory.append_to_section("profile", section, content)
        return f"Profile section '{section}' updated"

    async def _get_profile(self) -> str:
        return self.memory.read("profile")

    async def _remember_fact(self, fact: str, category: str = "notes") -> str:
        from moha_mind.utils.timezone import ksa_today_str

        dated_fact = f"- [{ksa_today_str()}] {fact}"
        self.memory.append_to_section(category, "Remembered", dated_fact)
        return f"Remembered: {fact}"

    async def _recall_facts(self, topic: str) -> str:
        results = self.memory.search(topic)
        if not results:
            return f"I don't remember anything about '{topic}' yet"
        return "\n".join(f"- [{r['category']}] {r['matched_line']}" for r in results[:10])

    async def _save_note(self, title: str, content: str) -> str:
        path = self.memory.save_note(title, content)
        return f"Note saved: {path.name}"

    async def _read_note(self, title: str) -> str:
        content = self.memory.read_note(title)
        return content if content else f"Note '{title}' not found"

    async def _list_notes(self) -> str:
        notes = self.memory.list_notes()
        if not notes:
            return "No notes saved"
        return "Notes:\n" + "\n".join(f"  - {n}" for n in notes)

    async def _save_daily_log(self, summary: str) -> str:
        self.memory.save_daily_log(summary)
        return "Daily log saved"

    async def _append_to_section(self, category: str, section: str, line: str) -> str:
        self.memory.append_to_section(category, section, line)
        return f"Added to {category} > {section}"
