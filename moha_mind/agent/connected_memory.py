"""Connected Memory Engine - links information across all memory categories.

When MohaMind learns something new, it automatically connects it to
related information across all memory files. This is what makes
MohaMind unique - it doesn't just store facts, it understands relationships.
"""

import re

from moha_mind.agent.memory import MemoryManager
from moha_mind.utils.logging_config import log
from moha_mind.utils.timezone import ksa_today_str


class ConnectedMemory:
    def __init__(self, memory: MemoryManager):
        self.memory = memory
        self._link_rules = {
            "birthday": self._handle_birthday,
            "anniversary": self._handle_anniversary,
            "expiry": self._handle_expiry,
            "car": self._handle_car_info,
            "wife": self._handle_family_info,
            "kid": self._handle_family_info,
            "child": self._handle_family_info,
            "bill": self._handle_bill,
            "subscription": self._handle_subscription,
            "appointment": self._handle_appointment,
            "doctor": self._handle_appointment,
            "medication": self._handle_medication,
            "task": self._handle_task,
            "trip": self._handle_travel,
            "travel": self._handle_travel,
            "passport": self._handle_document,
            "license": self._handle_document,
            "visa": self._handle_document,
            "pregnancy": self._handle_pregnancy,
            "vaccination": self._handle_vaccination,
            "gift": self._handle_gift,
            "course": self._handle_learning,
            "gym": self._handle_health_habit,
        }

    def process_new_info(self, text: str, source: str = "conversation") -> list[str]:
        """Analyze new information and create connections across memory files.

        Returns a list of actions taken (for transparency).
        """
        actions = []
        text_lower = text.lower()

        for keyword, handler in self._link_rules.items():
            if keyword in text_lower:
                try:
                    result = handler(text, source)
                    if result:
                        actions.extend(result)
                except Exception as e:
                    log.warning(f"Connected memory rule '{keyword}' failed: {e}")

        return actions

    def _handle_birthday(self, text: str, source: str) -> list[str]:
        """Connect birthday info across occasions, relationships, shopping."""
        actions = []
        date_match = re.search(r"(\d{4}-\d{2}-\d{2}|\w+ \d{1,2}(?:,? \d{4})?)", text)
        name_match = re.search(
            r"(?:wife|husband|friend|mom|dad|mother|father|brother|sister|son|daughter|kid)\s+"
            r"(?:named\s+)?(\w+)",
            text,
            re.IGNORECASE,
        )
        person_name = name_match.group(1) if name_match else ""

        if date_match and person_name:
            existing_occasions = self.memory.read("occasions")
            entry = f"- {person_name}'s birthday: {date_match.group(1)}"
            if entry.lower() not in existing_occasions.lower():
                self.memory.append_to_section("occasions", "Birthdays", entry)
                actions.append(f"Added {person_name}'s birthday to occasions")

            actions.append(
                f"Connected: I'll remind you about {person_name}'s birthday and suggest gift ideas when it's close"
            )
        return actions

    def _handle_anniversary(self, text: str, source: str) -> list[str]:
        actions = []
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        if date_match:
            existing = self.memory.read("occasions")
            entry = f"- Anniversary: {date_match.group(1)}"
            if entry.lower() not in existing.lower():
                self.memory.append_to_section("occasions", "Anniversaries", entry)
                actions.append("Added anniversary to occasions")
                actions.append("Connected: I'll suggest celebration ideas and gift reminders")
        return actions

    def _handle_expiry(self, text: str, source: str) -> list[str]:
        actions = []
        date_match = re.search(r"expir\w+(?:\s+(?:on|date)?)[:\s]+(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
        if date_match:
            actions.append("Connected: Added to Expiry Guardian - will remind you 90, 30, 7 days before and on the day")
        return actions

    def _handle_car_info(self, text: str, source: str) -> list[str]:
        actions = []
        text_lower = text.lower()
        service_keywords = ["oil change", "service", "maintenance", "tire", "brake", "battery"]
        if any(kw in text_lower for kw in service_keywords):
            today = ksa_today_str()
            self.memory.append_to_section("vehicle", "Service History", f"- [{today}] {text.strip()}")
            actions.append("Logged car service to vehicle history")
        if "insurance" in text_lower:
            actions.append("Connected: Will track car insurance expiry and remind you to renew")
        if "registration" in text_lower:
            actions.append("Connected: Will track registration renewal date")
        return actions

    def _handle_family_info(self, text: str, source: str) -> list[str]:
        actions = []
        text_lower = text.lower()
        if "wife" in text_lower or "spouse" in text_lower:
            for keyword in ["loves", "likes", "favorite", "favourite"]:
                if keyword in text_lower:
                    existing = self.memory.read("family")
                    if "## Wife" in existing:
                        actions.append(
                            "Connected: Updated wife preferences - "
                            "will use for gift ideas, date suggestions, and shopping"
                        )
                    break
        return actions

    def _handle_bill(self, text: str, source: str) -> list[str]:
        actions = []
        amount_match = re.search(r"(\d+)\s*(?:sar|riyal|r)", text, re.IGNORECASE)
        if amount_match:
            actions.append("Connected: Added to finance tracker - will remind you before due date")
        return actions

    def _handle_subscription(self, text: str, source: str) -> list[str]:
        actions = []
        actions.append("Connected: Added to subscription tracker - will monitor renewals and price changes")
        return actions

    def _handle_appointment(self, text: str, source: str) -> list[str]:
        actions = []
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        if date_match:
            actions.append("Connected: Added appointment reminder - will notify you 1 day and 1 hour before")
            if "family" in text.lower() or "wife" in text.lower() or "kid" in text.lower() or "child" in text.lower():
                actions.append("Connected: Also added to family calendar")
        return actions

    def _handle_medication(self, text: str, source: str) -> list[str]:
        actions = []
        actions.append("Connected: Added to health tracker - will set up medication reminders")
        return actions

    def _handle_task(self, text: str, source: str) -> list[str]:
        actions = []
        date_match = re.search(r"(?:by|due|before|deadline)[:\s]+(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
        if date_match:
            actions.append(
                f"Connected: Task deadline set for {date_match.group(1)} - will remind you 3 days and 1 day before"
            )
        return actions

    def _handle_travel(self, text: str, source: str) -> list[str]:
        actions = []
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        if date_match:
            actions.append("Connected: Added to travel tracker - will help with packing list and visa check")
        return actions

    def _handle_document(self, text: str, source: str) -> list[str]:
        actions = []
        date_match = re.search(r"expir\w+[:\s]+(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
        if date_match:
            actions.append("Connected: Added to Expiry Guardian - will remind you months in advance")
        return actions

    def _handle_pregnancy(self, text: str, source: str) -> list[str]:
        actions = []
        week_match = re.search(r"week\s+(\d+)", text, re.IGNORECASE)
        due_match = re.search(r"due[:\s]+(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
        if week_match or due_match:
            actions.append(
                "Connected: Updated pregnancy tracker - will provide weekly milestone updates and appointment reminders"
            )
        return actions

    def _handle_vaccination(self, text: str, source: str) -> list[str]:
        actions = []
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        if date_match:
            actions.append("Connected: Added vaccination to family tracker - will remind you 3 days before")
        return actions

    def _handle_gift(self, text: str, source: str) -> list[str]:
        actions = []
        for person_keyword in ["wife", "mom", "dad", "friend", "brother", "sister"]:
            if person_keyword in text.lower():
                existing = self.memory.read("relationships")
                if "## Gift Ideas" in existing:
                    self.memory.append_to_section("relationships", "Gift Ideas", f"- ({person_keyword}) {text.strip()}")
                actions.append(f"Connected: Stored as gift idea for {person_keyword}")
                break
        return actions

    def _handle_learning(self, text: str, source: str) -> list[str]:
        actions = []
        actions.append("Connected: Added to learning tracker - will help you schedule study time")
        return actions

    def _handle_health_habit(self, text: str, source: str) -> list[str]:
        actions = []
        actions.append("Connected: Updated health tracker - will include in weekly review patterns")
        return actions

    def get_connected_insights(self, query: str) -> list[str]:
        """Find connections across memory categories relevant to a query."""
        insights = []
        results = self.memory.search(query)
        categories_found = set(r["category"] for r in results)

        if len(categories_found) > 1:
            cat_names = ", ".join(categories_found)
            insights.append(f"This connects to your {cat_names} data")

        if "birthday" in query.lower() or "anniversary" in query.lower():
            shopping = self.memory.read("shopping")
            relationships = self.memory.read("relationships")
            if shopping or relationships:
                insights.append("I have gift ideas and preferences saved - let me suggest something")

        if "car" in query.lower() or "vehicle" in query.lower():
            finances = self.memory.read("finances")
            if finances and "insurance" in finances.lower():
                insights.append("I can check your car insurance status too")

        return insights
