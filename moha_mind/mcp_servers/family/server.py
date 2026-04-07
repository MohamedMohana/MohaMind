"""Family MCP Server - pregnancy tracker, kids, school events, vaccinations."""

import re
from datetime import datetime
from typing import Optional

from moha_mind.agent.memory import MemoryManager
from moha_mind.utils.timezone import now_ksa

PREGNANCY_MILESTONES = {
    4: "Missed period - pregnancy test positive",
    8: "First prenatal visit - blood work",
    12: "End of first trimester - screening tests",
    16: "Gender may be visible on ultrasound",
    20: "Anatomy scan (mid-pregnancy ultrasound)",
    24: "Viability milestone - baby can survive if born",
    26: "Glucose screening test (gestational diabetes)",
    28: "Third trimester begins - more frequent visits",
    32: "Baby's position check",
    36: "Group B Strep test",
    37: "Baby is considered early term",
    39: "Full term - ready any day!",
    40: "Due date",
}

VACCINATION_SCHEDULE = [
    {"age": "birth", "vaccines": ["Hepatitis B (1st dose)"]},
    {
        "age": "2 months",
        "vaccines": ["DTaP (1st)", "IPV (1st)", "Hib (1st)", "PCV13 (1st)", "Rotavirus (1st)", "Hep B (2nd)"],
    },
    {"age": "4 months", "vaccines": ["DTaP (2nd)", "IPV (2nd)", "Hib (2nd)", "PCV13 (2nd)", "Rotavirus (2nd)"]},
    {
        "age": "6 months",
        "vaccines": [
            "DTaP (3rd)",
            "IPV (3rd)",
            "Hib (3rd)",
            "PCV13 (3rd)",
            "Rotavirus (3rd)",
            "Hep B (3rd)",
            "Flu (annual)",
        ],
    },
    {"age": "12 months", "vaccines": ["MMR (1st)", "Varicella (1st)", "Hep A (1st)"]},
    {"age": "15 months", "vaccines": ["DTaP (4th)", "Hib (4th)", "PCV13 (4th)"]},
    {"age": "18 months", "vaccines": ["Hep A (2nd)", "MMR (2nd)", "Varicella (2nd)"]},
    {"age": "4-6 years", "vaccines": ["DTaP (5th)", "IPV (4th)", "MMR (2nd)", "Varicella (2nd)"]},
]


class FamilyServer:
    def __init__(self, memory: MemoryManager):
        self.memory = memory

    async def handle_tool(self, tool_name: str, arguments: dict) -> str:
        handlers = {
            "family_update_pregnancy_week": self._update_pregnancy_week,
            "family_add_appointment": self._add_appointment,
            "family_add_kid_event": self._add_kid_event,
            "family_get_upcoming": self._get_upcoming,
            "family_add_vaccination": self._add_vaccination,
            "family_get_vaccination_schedule": self._get_vaccination_schedule,
            "family_get_pregnancy_info": self._get_pregnancy_info,
        }
        handler = handlers.get(tool_name)
        if handler:
            return await handler(**arguments)
        return f"Unknown tool: {tool_name}"

    async def _update_pregnancy_week(self, week: Optional[int] = None) -> str:
        content = self.memory.read("family")
        if not content:
            return "No family data found"

        if week is None:
            due_match = re.search(r"[Dd]ue date:\s*(\d{4}-\d{2}-\d{2})", content)
            if due_match:
                due_date = datetime.strptime(due_match.group(1), "%Y-%m-%d")
                now = now_ksa().replace(tzinfo=None)
                weeks = int((280 - (due_date - now).days) / 7)
                week = max(1, min(42, weeks))
            else:
                return "Cannot calculate week - no due date found"

        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "Current week:" in line:
                lines[i] = f"- Current week: {week}"
                self.memory.write("family", "\n".join(lines))
                break

        milestone_msg = ""
        if week in PREGNANCY_MILESTONES:
            milestone_msg = f"\nMilestone: {PREGNANCY_MILESTONES[week]}"

        next_milestone = None
        for w in sorted(PREGNANCY_MILESTONES.keys()):
            if w > week:
                next_milestone = f"\nNext milestone (week {w}): {PREGNANCY_MILESTONES[w]}"
                break

        return f"Pregnancy updated to week {week}{milestone_msg}{next_milestone or ''}"

    async def _add_appointment(
        self, person: str, doctor: str, date: str, time: str = "", location: str = "", notes: str = ""
    ) -> str:
        entry = f"- [{date}] {person}: Dr. {doctor}"
        if time:
            entry += f" at {time}"
        if location:
            entry += f" - {location}"
        if notes:
            entry += f" ({notes})"
        self.memory.append_to_section("family", "Upcoming Appointments", entry)
        return f"Appointment added: {person} with Dr. {doctor} on {date}"

    async def _add_kid_event(self, kid_name: str, event: str, date: str, time: str = "") -> str:
        entry = f"- [{date}] {kid_name}: {event}"
        if time:
            entry += f" at {time}"
        self.memory.append_to_section("family", "Kids Events", entry)
        return f"Event added: {kid_name} - {event} on {date}"

    async def _get_upcoming(self, days_ahead: int = 14) -> str:
        content = self.memory.read("family")
        if not content:
            return "No family data found"
        today = now_ksa()
        upcoming = []
        for line in content.split("\n"):
            date_match = re.search(r"\[(\d{4}-\d{2}-\d{2})\]", line)
            if date_match:
                try:
                    event_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                    days = (event_date - today.replace(tzinfo=None)).days
                    if 0 <= days <= days_ahead:
                        upcoming.append(f"({days}d) {line.strip()}")
                except ValueError:
                    continue
        return "\n".join(upcoming) if upcoming else f"No family events in the next {days_ahead} days"

    async def _add_vaccination(self, kid_name: str, vaccine: str, date: str, next_due: str = "") -> str:
        entry = f"- [{date}] {kid_name}: {vaccine}"
        if next_due:
            entry += f" (next: {next_due})"
        self.memory.append_to_section("family", "Vaccination Log", entry)
        return f"Vaccination logged: {kid_name} - {vaccine}"

    async def _get_vaccination_schedule(self, age_months: Optional[int] = None) -> str:
        if age_months is not None:
            relevant = [s for s in VACCINATION_SCHEDULE if age_months <= 12]
        else:
            relevant = VACCINATION_SCHEDULE
        lines = []
        for schedule in relevant:
            lines.append(f"**Age {schedule['age']}:**")
            for v in schedule["vaccines"]:
                lines.append(f"  - {v}")
        return "\n".join(lines)

    async def _get_pregnancy_info(self, week: Optional[int] = None) -> str:
        if week and week in PREGNANCY_MILESTONES:
            return f"Week {week}: {PREGNANCY_MILESTONES[week]}"
        return "Milestones:\n" + "\n".join(f"- Week {w}: {m}" for w, m in sorted(PREGNANCY_MILESTONES.items()))
