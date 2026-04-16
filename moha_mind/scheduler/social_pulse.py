"""Social Pulse - nudges you to maintain relationships.

Checks when you last contacted people and sends reminders.
"""

from moha_mind.agent.memory import MemoryManager
from moha_mind.telegram_bot.bot import MohaMindBot
from moha_mind.utils.logging_config import log


def _days_ago(days: int) -> str:
    if days == 1:
        return "منذ يوم واحد"
    if days == 2:
        return "منذ يومين"
    if 3 <= days <= 10:
        return f"منذ {days} أيام"
    return f"منذ {days} يومًا"


class SocialPulse:
    def __init__(self, memory: MemoryManager, bot: MohaMindBot):
        self.memory = memory
        self.bot = bot

    async def check_and_nudge(self) -> None:
        """Check social connections and send nudges."""
        log.info("Social Pulse: checking connections...")

        content = self.memory.read("relationships")
        if not content:
            log.info("Social Pulse: no relationships tracked yet")
            return

        import re
        from datetime import datetime

        from moha_mind.utils.timezone import now_ksa

        today = now_ksa()
        nudges = []
        current_person = None
        current_data = {}

        for line in content.split("\n"):
            if line.startswith("### "):
                if current_person and current_data.get("days_since"):
                    nudges.append((current_person, current_data))
                current_person = line.replace("### ", "").strip()
                current_data = {}
            elif "Last contacted:" in line and current_person:
                date_match = re.search(r"(\d{4}-\d{2}-\d{2})", line)
                if date_match:
                    try:
                        last_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                        current_data["days_since"] = (today.replace(tzinfo=None) - last_date).days
                    except ValueError:
                        pass
                method_match = re.search(r"\((\w+)\)", line)
                if method_match:
                    current_data["last_method"] = method_match.group(1)

            elif "frequency:" in line.lower() and current_person:
                freq = line.lower()
                if "daily" in freq:
                    current_data["threshold"] = 2
                elif "weekly" in freq:
                    current_data["threshold"] = 10
                elif "monthly" in freq:
                    current_data["threshold"] = 35
                elif "quarterly" in freq:
                    current_data["threshold"] = 100
                else:
                    current_data["threshold"] = 35

        if current_person and current_data.get("days_since"):
            nudges.append((current_person, current_data))

        overdue = []
        for person, data in nudges:
            days = data.get("days_since", 0)
            threshold = data.get("threshold", 35)
            if days >= threshold:
                overdue.append((person, days, threshold))

        if not overdue:
            log.info("Social Pulse: all caught up!")
            return

        lines = ["📱 نبض العلاقات - حان وقت التواصل\n"]
        for person, days, threshold in sorted(overdue, key=lambda x: x[1], reverse=True)[:5]:
            lines.append(f"  - {person}: آخر تواصل {_days_ago(days)}")
            if days > 60:
                lines.append("    💡 مر وقت طويل. قد يكون مناسبًا إرسال رسالة أو ترتيب مكالمة.")

        lines.append("\nاستخدم \u200e/social لرؤية التفاصيل أو أخبرني بتسجيل تواصل جديد.")

        from moha_mind.telegram_bot.formatters import truncate_message

        message = "\n".join(lines)
        for part in truncate_message(message):
            await self.bot.send_message(part)

        log.info(f"Social Pulse: sent {len(overdue)} nudges")
