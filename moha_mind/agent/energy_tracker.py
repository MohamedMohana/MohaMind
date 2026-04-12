"""Energy and mood pattern tracker.

Learns from user behavior and conversation patterns to understand
when they're most productive, when they need breaks, and adjusts
scheduling suggestions accordingly.
"""

import re

from moha_mind.agent.memory import MemoryManager
from moha_mind.utils.timezone import ksa_today_str, now_ksa


class EnergyTracker:
    def __init__(self, memory: MemoryManager):
        self.memory = memory

    def analyze_message_mood(self, message: str) -> str:
        """Simple mood detection from user messages."""
        text = message.lower()

        high_energy_words = [
            "great",
            "awesome",
            "excited",
            "amazing",
            "fantastic",
            "love",
            "energetic",
            "motivated",
            "productive",
            "let's do it",
            "happy",
            "wonderful",
        ]
        low_energy_words = [
            "tired",
            "exhausted",
            "stressed",
            "overwhelmed",
            "busy",
            "headache",
            "sick",
            "lazy",
            "bored",
            "annoyed",
            "frustrated",
            "anxious",
            "worried",
            "sad",
        ]

        high_count = sum(1 for w in high_energy_words if w in text)
        low_count = sum(1 for w in low_energy_words if w in text)

        if high_count > low_count:
            return "high"
        elif low_count > high_count:
            return "low"
        return "neutral"

    def log_interaction(self, message: str, response_length: int) -> None:
        """Log an interaction for pattern analysis."""
        hour = now_ksa().hour
        mood = self.analyze_message_mood(message)
        today = ksa_today_str()

        existing = self.memory.read("energy_log")
        entry = (
            f"- [{today} {hour}:00] Mood: {mood} | Message length: {len(message)} | Response length: {response_length}"
        )

        if "## Raw Data" not in existing:
            existing += "\n\n## Raw Data\n"
        self.memory.append_to_section("energy_log", "Raw Data", entry)

    def get_productive_hours(self) -> list[int]:
        """Analyze historical data to find most productive hours."""
        content = self.memory.read("energy_log")
        if not content:
            return [9, 10, 11]

        hour_mood = {}
        for line in content.split("\n"):
            match = re.search(r"(\d{1,2}):00\] Mood: (\w+)", line)
            if match:
                hour = int(match.group(1))
                mood = match.group(2)
                if hour not in hour_mood:
                    hour_mood[hour] = {"high": 0, "neutral": 0, "low": 0}
                if mood in hour_mood[hour]:
                    hour_mood[hour][mood] += 1

        if not hour_mood:
            return [9, 10, 11]

        scored = []
        for hour, moods in hour_mood.items():
            score = moods.get("high", 0) * 2 + moods.get("neutral", 0) - moods.get("low", 0)
            scored.append((hour, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [h for h, _ in scored[:3]]

    def get_energy_suggestion(self) -> str:
        """Get a time-based energy suggestion for the current moment."""
        hour = now_ksa().hour
        productive_hours = self.get_productive_hours()

        if hour in productive_hours:
            return "You're usually at your best right now - great time for focused work!"
        elif hour < 7:
            return "It's early - consider light tasks or planning your day"
        elif 12 <= hour <= 13:
            return "Post-lunch dip - consider a short walk or lighter tasks"
        elif hour >= 22:
            return "Getting late - wrap up and prepare for tomorrow"
        else:
            return "Steady energy period - good for regular tasks"
