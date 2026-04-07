"""Memory manager - reads and writes structured markdown memory files.

This is MohaMind's persistent brain. All personal data is stored as
human-readable markdown files that can be directly edited by the user.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from moha_mind.config import settings
from moha_mind.utils.logging_config import log
from moha_mind.utils.timezone import ksa_today_str, now_ksa

MEMORY_FILES = {
    "profile": "profile.md",
    "family": "family.md",
    "tasks": "tasks.md",
    "occasions": "occasions.md",
    "vehicle": "vehicle.md",
    "finances": "finances.md",
    "health": "health.md",
    "home": "home.md",
    "documents": "documents.md",
    "travel": "travel.md",
    "learning": "learning.md",
    "shopping": "shopping.md",
    "relationships": "relationships.md",
    "energy_log": "energy_log.md",
}


class MemoryManager:
    def __init__(self, memory_dir: Optional[str] = None):
        self.memory_path = Path(memory_dir or settings.memory_dir)
        self.memory_path.mkdir(parents=True, exist_ok=True)
        (self.memory_path / "daily_log").mkdir(exist_ok=True)
        (self.memory_path / "notes").mkdir(exist_ok=True)

    def read(self, category: str) -> str:
        """Read a memory file by category name."""
        filename = MEMORY_FILES.get(category, f"{category}.md")
        filepath = self.memory_path / filename
        if filepath.exists():
            return filepath.read_text(encoding="utf-8")
        return ""

    def write(self, category: str, content: str) -> None:
        """Overwrite a memory file."""
        filename = MEMORY_FILES.get(category, f"{category}.md")
        filepath = self.memory_path / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content.strip() + "\n", encoding="utf-8")
        log.info(f"Memory updated: {category}")

    def append(self, category: str, content: str) -> None:
        """Append content to a memory file."""
        existing = self.read(category)
        if existing and not existing.endswith("\n"):
            existing += "\n"
        self.write(category, existing + content)

    def append_to_section(self, category: str, section_header: str, line: str) -> None:
        """Append a line under a specific ## section in a memory file."""
        content = self.read(category)
        if not content:
            self.write(category, f"# {category.title()}\n\n## {section_header}\n{line}\n")
            return

        section_pattern = f"## {section_header}"
        if section_pattern in content:
            parts = content.split(section_pattern, 1)
            after = parts[1]
            self.write(category, parts[0] + section_pattern + after.rstrip() + f"\n{line}\n")
        else:
            self.write(category, content.rstrip() + f"\n\n## {section_header}\n{line}\n")

    def search(self, query: str, categories: Optional[list[str]] = None) -> list[dict]:
        """Search across memory files for a keyword/phrase."""
        results = []
        cats = categories or list(MEMORY_FILES.keys())
        query_lower = query.lower()

        for cat in cats:
            content = self.read(cat)
            if not content:
                continue
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if query_lower in line.lower():
                    context_start = max(0, i - 1)
                    context_end = min(len(lines), i + 2)
                    results.append(
                        {
                            "category": cat,
                            "line_number": i + 1,
                            "matched_line": line,
                            "context": "\n".join(lines[context_start:context_end]),
                        }
                    )
        return results

    def get_all_context(self, categories: Optional[list[str]] = None) -> str:
        """Get combined content from multiple memory categories for LLM context."""
        cats = categories or ["profile", "family", "tasks", "occasions", "vehicle", "finances", "health"]
        parts = []
        for cat in cats:
            content = self.read(cat)
            if content.strip():
                parts.append(f"### {cat.upper()}\n{content}")
        return "\n\n".join(parts)

    def save_daily_log(self, summary: str) -> None:
        """Save a daily conversation/activity summary."""
        today = ksa_today_str()
        filepath = self.memory_path / "daily_log" / f"{today}.md"
        existing = ""
        if filepath.exists():
            existing = filepath.read_text(encoding="utf-8")
        entry = f"\n## Log Entry ({now_ksa().strftime('%H:%M')})\n{summary}\n"
        filepath.write_text((existing + entry).strip() + "\n", encoding="utf-8")

    def save_note(self, title: str, content: str) -> Path:
        """Save a free-form note."""
        safe_title = re.sub(r"[^\w\s-]", "", title).replace(" ", "_").lower()
        filepath = self.memory_path / "notes" / f"{safe_title}.md"
        filepath.write_text(f"# {title}\n\n{content}\n", encoding="utf-8")
        return filepath

    def list_notes(self) -> list[str]:
        """List all saved notes."""
        notes_dir = self.memory_path / "notes"
        if not notes_dir.exists():
            return []
        return [f.stem for f in notes_dir.glob("*.md")]

    def read_note(self, title: str) -> str:
        safe_title = re.sub(r"[^\w\s-]", "", title).replace(" ", "_").lower()
        filepath = self.memory_path / "notes" / f"{safe_title}.md"
        if filepath.exists():
            return filepath.read_text(encoding="utf-8")
        return ""

    def get_task_section(self) -> list[dict]:
        """Parse tasks from tasks.md into structured data."""
        content = self.read("tasks")
        if not content:
            return []
        tasks = []
        current_task = None
        for line in content.split("\n"):
            task_match = re.match(r"^- \[([ x])\] (.+)$", line)
            if task_match:
                if current_task:
                    tasks.append(current_task)
                done = task_match.group(1) == "x"
                full_text = task_match.group(2).strip()
                priority = "medium"
                due = None
                if "[HIGH]" in full_text:
                    priority = "high"
                elif "[LOW]" in full_text:
                    priority = "low"
                due_match = re.search(r"due:(\d{4}-\d{2}-\d{2})", full_text)
                if due_match:
                    due = due_match.group(1)
                current_task = {
                    "text": full_text.replace("[HIGH]", "")
                    .replace("[LOW]", "")
                    .replace("[MED]", "")
                    .replace("due:" + (due or ""), "")
                    .strip(),
                    "done": done,
                    "priority": priority,
                    "due": due,
                }
        if current_task:
            tasks.append(current_task)
        return tasks

    def add_task(self, text: str, priority: str = "medium", due: Optional[str] = None) -> None:
        """Add a new task to tasks.md."""
        content = self.read("tasks")
        if not content:
            content = "# Tasks\n\n## Active\n"
        priority_tag = f"[{priority.upper()}]" if priority != "medium" else ""
        due_tag = f" due:{due}" if due else ""
        task_line = f"- [ ] {text} {priority_tag}{due_tag}".strip()
        if "## Active" in content:
            self.append_to_section("tasks", "Active", task_line)
        else:
            self.append("tasks", f"\n## Active\n{task_line}")

    def complete_task(self, task_text: str) -> bool:
        """Mark a task as complete."""
        content = self.read("tasks")
        if not content:
            return False
        if task_text in content and f"- [ ] {task_text}" in content:
            content = content.replace(f"- [ ] {task_text}", f"- [x] {task_text}")
            self.write("tasks", content)
            return True
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "- [ ]" in line and task_text.lower() in line.lower():
                lines[i] = line.replace("- [ ]", "- [x]", 1)
                self.write("tasks", "\n".join(lines))
                return True
        return False

    def get_expiring_items(self, days_ahead: int = 90) -> list[dict]:
        """Scan all memory files for items with expiry dates."""
        from moha_mind.utils.timezone import days_until

        results = []
        expiry_patterns = [
            (r"[Ee]xpir(?:e|y|es|ation)[:\s]+(\d{4}-\d{2}-\d{2})", "expiry"),
            (r"[Dd]ue[:\s]+(\d{4}-\d{2}-\d{2})", "due"),
            (r"[Rr]enew(?:al)?[:\s]+(\d{4}-\d{2}-\d{2})", "renewal"),
            (r"[Vv]alid (?:until|till|to)[:\s]+(\d{4}-\d{2}-\d{2})", "validity"),
        ]

        scan_categories = ["documents", "vehicle", "finances", "health", "home"]
        for cat in scan_categories:
            content = self.read(cat)
            if not content:
                continue
            lines = content.split("\n")
            for line in lines:
                for pattern, exp_type in expiry_patterns:
                    match = re.search(pattern, line)
                    if match:
                        date_str = match.group(1)
                        try:
                            exp_date = datetime.strptime(date_str, "%Y-%m-%d")
                            days = days_until(exp_date)
                            if 0 <= days <= days_ahead:
                                results.append(
                                    {
                                        "category": cat,
                                        "type": exp_type,
                                        "date": date_str,
                                        "days_left": days,
                                        "detail": line.strip(),
                                    }
                                )
                        except ValueError:
                            continue
        results.sort(key=lambda x: x["days_left"])
        return results

    def ensure_templates(self) -> None:
        """Create template memory files if they don't exist."""
        templates = {
            "profile": (
                "# My Profile\n\n"
                "## Personal\n- Name: \n- Birthday: \n- Nationality: \n"
                "- Location: Saudi Arabia\n\n"
                "## Preferences\n- Clothing sizes: \n- Shoe size: \n"
                "- Favorite food: \n- Allergies: None\n\n"
                "## Work\n- Company: \n- Role: \n- Work hours: \n\n"
                "## Habits & Patterns\n- Wake up time: \n- Sleep time: \n"
                "- Most productive: Morning\n- Gym days: \n"
            ),
            "family": (
                "# Family\n\n## Wife\n- Name: \n- Birthday: \n- Loves: \n"
                "- Clothing size: \n- Shoe size: \n\n"
                "## Pregnancy Tracker\n- Due date: \n- Current week: \n"
                "- Next appointment: \n- Milestones:\n\n"
                "## Kids\n### Child 1\n- Name: \n- Age: \n- School: \n"
                "- Clothing size: \n- Shoe size: \n"
                "- Vaccinations up to date: \n- Next appointment: \n"
            ),
            "tasks": (
                "# Tasks\n\n## Active\n"
                "<!-- Add tasks here: - [ ] Task name [HIGH/MED/LOW] due:YYYY-MM-DD -->\n\n"
                "## Recurring\n"
                "<!-- Tasks that repeat: - [ ] Weekly task (every Monday) -->\n\n"
                "## Completed\n"
                "<!-- Done tasks: - [x] Completed task -->\n"
            ),
            "occasions": (
                "# Important Occasions\n\n## Birthdays\n"
                "<!-- - Person Name: YYYY-MM-DD -->\n\n"
                "## Anniversaries\n<!-- - Event: YYYY-MM-DD -->\n\n"
                "## Annual Events\n<!-- - Event name: MM-DD (recurring) -->\n"
            ),
            "vehicle": (
                "# Vehicle\n\n## Details\n- Make/Model: \n- Year: \n"
                "- Plate: \n- Color: \n- VIN: \n- Mileage: \n\n"
                "## Registration\n- Expires: \n- Renewal reminder: \n\n"
                "## Insurance\n- Provider: \n- Policy #: \n- Expires: \n"
                "- Premium: \n\n"
                "## Service History\n"
                "<!-- - [YYYY-MM-DD] Service type - Location - Mileage -->\n\n"
                "## Next Service\n- Due date: \n- Due mileage: \n"
            ),
            "finances": (
                "# Finances\n\n## Salary\n- Company: \n- Amount: \n"
                "- Deposit date: 27th monthly\n\n"
                "## Monthly Bills\n"
                "<!-- - [Provider] Amount SAR - Due: DDth - Auto-pay: Yes/No -->\n\n"
                "## Subscriptions\n"
                "<!-- - [Service] Amount/month - Renews: DDth -->\n\n"
                "## Insurance Policies\n"
                "<!-- - [Type] Provider - Expires: YYYY-MM-DD -->\n"
            ),
            "health": (
                "# Health\n\n## Medications\n"
                "<!-- - Medication name: dosage, frequency -->\n\n"
                "## Doctors\n"
                "<!-- - Dr. Name (Specialty) - Phone - Next visit: -->\n\n"
                "## Gym\n- Schedule: \n"
                "- Membership expires: \n\n## Health Goals\n"
                "- Target weight: \n- Diet plan: \n"
            ),
            "home": (
                "# Home\n\n## Details\n- Address: \n- Rent: SAR/month\n"
                "- Rent due: 1st monthly\n\n## Utilities\n"
                "<!-- - [Utility] Average amount - Due date -->\n\n"
                "## Appliances & Warranties\n"
                "<!-- - [Appliance] Brand - Warranty expires: YYYY-MM-DD -->\n\n"
                "## Maintenance Log\n"
                "<!-- - [YYYY-MM-DD] Issue - Resolution -->\n"
            ),
            "documents": (
                "# Documents\n\n## Passport\n- Number: \n- Expires: \n\n"
                "## National ID\n- Number: \n- Expires: \n\n"
                "## Driver License\n- Number: \n- Expires: \n\n"
                "## Visa\n- Type: \n- Expires: \n\n"
                "## Other Documents\n"
                "<!-- - Document name - Location - Expires -->\n"
            ),
            "travel": (
                "# Travel\n\n## Upcoming Trips\n"
                "<!-- - Destination: YYYY-MM-DD to YYYY-MM-DD -->\n\n"
                "## Visa Requirements\n"
                "<!-- - Country: visa status -->\n\n"
                "## Travel Bucket List\n"
                "<!-- - Destination - Why -->\n"
            ),
            "learning": (
                "# Learning & Growth\n\n## Current Courses\n"
                "<!-- - Course name - Platform - Progress: X% -->\n\n"
                "## Reading List\n"
                "<!-- - Book title - Author - Status: reading/want to read/finished -->\n\n"
                "## Skills Goals\n"
                "<!-- - Skill - Target level - Current level -->\n\n"
                "## Certifications\n"
                "<!-- - Cert name - Expires: YYYY-MM-DD -->\n"
            ),
            "shopping": (
                "# Shopping\n\n## Shopping List\n"
                "<!-- - Item to buy -->\n\n## Preferred Brands\n"
                "<!-- - Category: Brand -->\n\n"
                "## Sizes (Self)\n- Tops: \n- Pants: \n- Shoes: \n\n"
                "## Sizes (Family)\n<!-- - Person: category = size -->\n"
            ),
            "relationships": (
                "# Relationships\n\n## Close Friends\n"
                "<!-- ### Name\n- Last contacted: YYYY-MM-DD\n"
                "- Birthday: YYYY-MM-DD\n"
                "- Contact frequency: weekly/monthly\n- Notes: \n-->\n\n"
                "## Extended Family\n"
                "<!-- ### Name\n- Relationship: \n- Birthday: \n"
                "- Last contacted: \n-->\n\n"
                "## Gift Ideas\n<!-- - Person: idea -->\n"
            ),
            "energy_log": (
                "# Energy & Mood Log\n\n## Patterns\n"
                "<!-- Discovered patterns about energy/mood will be logged here -->\n\n"
                "## Observations\n"
                "<!-- - [YYYY-MM-DD] Observation -->\n"
            ),
        }
        for category, template in templates.items():
            filepath = self.memory_path / MEMORY_FILES[category]
            if not filepath.exists():
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_text(template, encoding="utf-8")
                log.info(f"Created template: {category}")
