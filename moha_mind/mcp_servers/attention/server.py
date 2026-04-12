import re
from datetime import datetime

from moha_mind.agent.memory import MemoryManager
from moha_mind.utils.occasions import upcoming_occasions
from moha_mind.utils.timezone import days_until, now_ksa


class AttentionServer:
    def __init__(self, memory: MemoryManager):
        self.memory = memory

    async def handle_tool(self, tool_name: str, arguments: dict) -> str:
        handlers = {
            "get_attention_radar": self._get_attention_radar,
        }
        handler = handlers.get(tool_name)
        if handler:
            return await handler(**arguments)
        return f"Unknown tool: {tool_name}"

    def _task_signals(self, days_ahead: int) -> list[dict]:
        priority_weight = {"high": 12, "medium": 7, "low": 3}
        signals = []

        for task in self.memory.get_task_section():
            if task["done"] or not task["due"]:
                continue

            try:
                due_date = datetime.strptime(task["due"], "%Y-%m-%d")
            except ValueError:
                continue

            days = days_until(due_date)
            if days > days_ahead:
                continue

            base_score = 70 + priority_weight.get(task["priority"], 5)
            if days < 0:
                base_score = 120 + max(days, -20)
                timing = f"overdue by {abs(days)}d"
                icon = "🚨"
            elif days == 0:
                base_score = 112 + priority_weight.get(task["priority"], 5)
                timing = "today"
                icon = "🔥"
            elif days == 1:
                base_score = 102 + priority_weight.get(task["priority"], 5)
                timing = "tomorrow"
                icon = "⏳"
            else:
                base_score -= days
                timing = f"in {days}d"
                icon = "📋"

            signals.append(
                {
                    "score": base_score,
                    "bucket": "Immediate" if base_score >= 95 else "Soon",
                    "icon": icon,
                    "title": task["text"],
                    "detail": f"task due {timing}",
                }
            )

        return signals

    def _reminder_signals(self, days_ahead: int) -> list[dict]:
        signals = []
        for reminder in self.memory.get_reminder_section():
            remind_at = reminder.get("remind_at", "")
            if not remind_at:
                continue
            try:
                remind_dt = datetime.strptime(remind_at, "%Y-%m-%d %H:%M")
            except ValueError:
                continue

            days = days_until(remind_dt)
            if days > days_ahead:
                continue

            if days < 0:
                score = 106
                timing = "overdue"
                icon = "🚨"
            elif days == 0:
                score = 98
                timing = "today"
                icon = "⏰"
            elif days == 1:
                score = 92
                timing = "tomorrow"
                icon = "🔔"
            else:
                score = 76 - min(days, 20)
                timing = f"in {days}d"
                icon = "🕰️"

            event_suffix = f" → {reminder['event_at']}" if reminder.get("event_at") else ""
            signals.append(
                {
                    "score": score,
                    "bucket": "Immediate" if score >= 95 else "Soon",
                    "icon": icon,
                    "title": reminder["text"],
                    "detail": f"reminder {timing}{event_suffix}",
                }
            )

        return signals

    def _expiry_signals(self, days_ahead: int) -> list[dict]:
        signals = []
        for item in self.memory.get_expiring_items(days_ahead):
            days = item["days_left"]
            if days == 0:
                score = 108
                icon = "🛑"
                timing = "today"
            elif days == 1:
                score = 100
                icon = "⚠️"
                timing = "tomorrow"
            else:
                score = 88 - min(days, 20)
                icon = "📄"
                timing = f"in {days}d"

            signals.append(
                {
                    "score": score,
                    "bucket": "Immediate" if score >= 95 else "Soon",
                    "icon": icon,
                    "title": item["detail"],
                    "detail": f"{item['category']} expires {timing}",
                }
            )
        return signals

    def _occasion_signals(self, days_ahead: int) -> list[dict]:
        content = self.memory.read("occasions")
        signals = []

        for entry in upcoming_occasions(content, days_ahead=min(days_ahead, 45)):
            if entry.days_left == 0:
                score = 101
                icon = "🎉"
                timing = "today"
            elif entry.days_left == 1:
                score = 96
                icon = "🎁"
                timing = "tomorrow"
            else:
                score = 82 - min(entry.days_left, 20)
                icon = "🎂" if entry.kind == "birthday" else "💍" if entry.kind == "anniversary" else "📅"
                timing = f"in {entry.days_left}d"

            signals.append(
                {
                    "score": score,
                    "bucket": "Immediate" if score >= 95 else "Soon",
                    "icon": icon,
                    "title": entry.title,
                    "detail": f"{entry.kind.replace('_', ' ')} {timing}",
                }
            )

        return signals

    def _family_signals(self, days_ahead: int) -> list[dict]:
        content = self.memory.read("family")
        if not content:
            return []

        signals = []
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped.startswith("- ["):
                continue

            date_match = re.search(r"\[(\d{4}-\d{2}-\d{2})\]", stripped)
            if not date_match:
                continue

            try:
                event_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
            except ValueError:
                continue

            days = days_until(event_date)
            if not 0 <= days <= days_ahead:
                continue

            if days == 0:
                score = 97
                timing = "today"
            elif days == 1:
                score = 92
                timing = "tomorrow"
            else:
                score = 78 - min(days, 20)
                timing = f"in {days}d"

            signals.append(
                {
                    "score": score,
                    "bucket": "Immediate" if score >= 95 else "Soon",
                    "icon": "👨‍👩‍👧‍👦",
                    "title": stripped,
                    "detail": f"family event {timing}",
                }
            )

        return signals

    def _social_signals(self) -> list[dict]:
        content = self.memory.read("relationships")
        if not content:
            return []

        thresholds = {
            "daily": 2,
            "weekly": 10,
            "monthly": 35,
            "quarterly": 100,
        }
        today = now_ksa().replace(tzinfo=None)
        current_name = None
        current_frequency = "monthly"
        current_last_contact = None
        signals = []

        def flush() -> None:
            if not current_name or not current_last_contact:
                return
            days_since = (today - current_last_contact).days
            threshold = thresholds.get(current_frequency, 35)
            if days_since < threshold:
                return
            score = 58 + min(days_since - threshold, 20)
            signals.append(
                {
                    "score": score,
                    "bucket": "Keep Warm",
                    "icon": "🤝",
                    "title": current_name,
                    "detail": f"last contact {days_since}d ago",
                }
            )

        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("### "):
                flush()
                current_name = stripped[4:].strip()
                current_frequency = "monthly"
                current_last_contact = None
                continue

            if not current_name:
                continue

            if "Contact frequency:" in stripped:
                current_frequency = stripped.split(":", 1)[1].strip().lower()
            elif "Last contacted:" in stripped:
                match = re.search(r"(\d{4}-\d{2}-\d{2})", stripped)
                if match:
                    try:
                        current_last_contact = datetime.strptime(match.group(1), "%Y-%m-%d")
                    except ValueError:
                        current_last_contact = None

        flush()
        return signals

    def _collect_signals(self, days_ahead: int) -> list[dict]:
        signals = []
        signals.extend(self._task_signals(days_ahead))
        signals.extend(self._reminder_signals(days_ahead))
        signals.extend(self._expiry_signals(days_ahead))
        signals.extend(self._occasion_signals(days_ahead))
        signals.extend(self._family_signals(min(days_ahead, 14)))
        signals.extend(self._social_signals())
        return sorted(signals, key=lambda item: (-item["score"], item["title"].lower()))

    async def _get_attention_radar(self, days_ahead: int = 30, limit: int = 8) -> str:
        signals = self._collect_signals(days_ahead)
        if not signals:
            return "🎯 Attention Radar is calm. Nothing urgent is pulling on your attention right now."

        buckets = {
            "Immediate": [],
            "Soon": [],
            "Keep Warm": [],
        }
        for signal in signals[:limit]:
            buckets[signal["bucket"]].append(signal)

        lines = ["🎯 Attention Radar", ""]
        for bucket in ("Immediate", "Soon", "Keep Warm"):
            items = buckets[bucket]
            if not items:
                continue
            lines.append(f"{bucket}:")
            for item in items:
                lines.append(f"- {item['icon']} {item['title']} — {item['detail']}")
            lines.append("")

        return "\n".join(lines).strip()
