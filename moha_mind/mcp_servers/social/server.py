"""Social MCP Server - relationships, gifts, social pulse."""

import re
from datetime import datetime

from moha_mind.agent.memory import MemoryManager
from moha_mind.utils.date_helpers import next_occurrence
from moha_mind.utils.timezone import days_until, ksa_today_str, now_ksa


class SocialServer:
    def __init__(self, memory: MemoryManager):
        self.memory = memory

    async def handle_tool(self, tool_name: str, arguments: dict) -> str:
        handlers = {
            "social_add_person": self._add_person,
            "social_log_contact": self._log_contact,
            "social_get_neglected": self._get_neglected,
            "social_add_gift_idea": self._add_gift_idea,
            "social_get_gift_ideas": self._get_gift_ideas,
            "social_get_upcoming_birthdays": self._get_upcoming_birthdays,
        }
        handler = handlers.get(tool_name)
        if handler:
            return await handler(**arguments)
        return f"Unknown tool: {tool_name}"

    async def _add_person(
        self,
        name: str,
        relationship: str = "",
        birthday: str = "",
        contact_frequency: str = "monthly",
        notes: str = "",
        category: str = "Close Friends",
    ) -> str:
        entry_parts = [f"### {name}"]
        if relationship:
            entry_parts.append(f"- Relationship: {relationship}")
        if birthday:
            entry_parts.append(f"- Birthday: {birthday}")
        entry_parts.append(f"- Last contacted: {ksa_today_str()}")
        entry_parts.append(f"- Contact frequency: {contact_frequency}")
        if notes:
            entry_parts.append(f"- Notes: {notes}")
        entry = "\n".join(entry_parts)

        section = "Close Friends" if category == "Close Friends" else category
        self.memory.append_to_section("relationships", section, entry)

        if birthday:
            occasion_entry = f"- {name}'s birthday: {birthday}"
            self.memory.append_to_section("occasions", "Birthdays", occasion_entry)

        return f"Person added: {name}" + (" (birthday tracked)" if birthday else "")

    async def _log_contact(self, name: str, method: str = "message", notes: str = "") -> str:
        content = self.memory.read("relationships")
        if not content:
            return "No relationships data found"

        lines = content.split("\n")
        found = False
        for i, line in enumerate(lines):
            if f"### {name}" in line or name.lower() in line.lower():
                for j in range(i + 1, min(i + 8, len(lines))):
                    if "Last contacted:" in lines[j]:
                        lines[j] = f"- Last contacted: {ksa_today_str()} ({method})"
                        found = True
                        break
                if not found:
                    lines.insert(i + 1, f"- Last contacted: {ksa_today_str()} ({method})")
                    found = True
                break

        if found:
            self.memory.write("relationships", "\n".join(lines))
            if notes:
                self.memory.append_to_section("relationships", name, f"  - Note: [{ksa_today_str()}] {notes}")
            return f"Contact logged: {name} ({method})"
        return f"Person not found: {name}. Add them first with social_add_person"

    async def _get_neglected(self, days_threshold: int = 30) -> str:
        content = self.memory.read("relationships")
        if not content:
            return "No relationships tracked yet"

        today = now_ksa()
        neglected = []
        current_person = None
        current_data = {}

        for line in content.split("\n"):
            if line.startswith("### "):
                if current_person and current_data:
                    neglected.append((current_person, current_data))
                current_person = line.replace("### ", "").strip()
                current_data = {}
            elif "Last contacted:" in line and current_person:
                date_match = re.search(r"(\d{4}-\d{2}-\d{2})", line)
                if date_match:
                    try:
                        last_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                        current_data["days_since"] = (today.replace(tzinfo=None) - last_date).days
                    except ValueError:
                        current_data["days_since"] = 999
                freq_match = re.search(
                    r"frequency:\s*(\w+)",
                    content[max(0, content.find(current_person)) : content.find(current_person) + 500]
                    if current_person in content
                    else "",
                )
                current_data["frequency"] = freq_match.group(1) if freq_match else "monthly"
                if "notes" in line.lower():
                    current_data["notes"] = line

        if current_person and current_data:
            neglected.append((current_person, current_data))

        results = []
        for person, data in neglected:
            days = data.get("days_since", 999)
            if days >= days_threshold:
                results.append(f"- {person}: Last contact {days} days ago (target: {data.get('frequency', 'monthly')})")

        if not results:
            return "You're all caught up with your contacts!"
        return "📞 People to reach out to:\n" + "\n".join(results)

    async def _add_gift_idea(self, person: str, idea: str, occasion: str = "", estimated_cost: str = "") -> str:
        entry = f"- ({person}) {idea}"
        if occasion:
            entry += f" [{occasion}]"
        if estimated_cost:
            entry += f" (~{estimated_cost} SAR)"
        self.memory.append_to_section("relationships", "Gift Ideas", entry)
        return f"Gift idea saved: {idea} for {person}"

    async def _get_gift_ideas(self, person: str = "") -> str:
        content = self.memory.read("relationships")
        if not content or "## Gift Ideas" not in content:
            return "No gift ideas saved yet"

        lines = content.split("\n")
        in_section = False
        ideas = []
        for line in lines:
            if "## Gift Ideas" in line:
                in_section = True
                continue
            if in_section and line.startswith("##"):
                break
            if in_section and line.strip():
                if not person or person.lower() in line.lower():
                    ideas.append(line.strip())

        if not ideas:
            return f"No gift ideas for {person}" if person else "No gift ideas saved"
        return "\n".join(ideas)

    async def _get_upcoming_birthdays(self, days_ahead: int = 30) -> str:
        content = self.memory.read("occasions")
        if not content:
            return "No occasions tracked yet"

        today = now_ksa()
        upcoming = []
        for line in content.split("\n"):
            if "birthday" not in line.lower():
                continue
            date_match = re.search(r"(\d{4}-)?(\d{2}-\d{2})", line)
            if date_match:
                month = int(date_match.group(2).split("-")[0])
                day = int(date_match.group(2).split("-")[1])
                next_date = next_occurrence(month, day, today)
                days = days_until(next_date)
                if 0 <= days <= days_ahead:
                    name_match = re.match(r"-\s*(.+?)\s*(?:birthday|Birthday)", line)
                    name = name_match.group(1).strip() if name_match else line.strip()
                    upcoming.append(f"- {name}: in {days} days ({next_date.strftime('%B %d')})")

        if not upcoming:
            return f"No birthdays in the next {days_ahead} days"
        return "🎂 Upcoming birthdays:\n" + "\n".join(
            sorted(upcoming, key=lambda x: int(x.split("in ")[1].split(" ")[0]))
        )
