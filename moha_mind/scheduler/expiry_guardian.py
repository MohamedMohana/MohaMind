"""Expiry Guardian - proactively tracks everything with an expiry date.

Scans all memory files and sends alerts at 90, 30, 7, and 0 days before expiry.
"""

from moha_mind.agent.memory import MemoryManager
from moha_mind.telegram_bot.bot import MohaMindBot
from moha_mind.telegram_bot.formatters import truncate_message
from moha_mind.utils.i18n import days_left_phrase, t
from moha_mind.utils.logging_config import log


class ExpiryGuardian:
    def __init__(self, memory: MemoryManager, bot: MohaMindBot):
        self.memory = memory
        self.bot = bot

    async def check_and_alert(self) -> None:
        """Check all expiring items and send alerts if needed."""
        log.info("Expiry Guardian: running daily check...")

        items = self.memory.get_expiring_items(days_ahead=90)
        if not items:
            log.info("Expiry Guardian: nothing expiring")
            return

        urgent = [i for i in items if i["days_left"] <= 7]
        warning = [i for i in items if 7 < i["days_left"] <= 30]
        info = [i for i in items if 30 < i["days_left"] <= 90]

        alert_lines = []

        if urgent:
            alert_lines.append(t("expiry.urgent_header"))
            for item in urgent:
                if item["days_left"] == 0:
                    alert_lines.append(f"  ⚠️ {t('expiry.today')}: {item['detail']}")
                else:
                    alert_lines.append(f"  ⚠️ {days_left_phrase(item['days_left'])}: {item['detail']}")

        if warning:
            alert_lines.append("\n" + t("expiry.month_header"))
            for item in warning:
                alert_lines.append(f"  - {days_left_phrase(item['days_left'])}: {item['detail']}")

        if info and len(info) <= 3:
            alert_lines.append("\n" + t("expiry.quarter_header"))
            for item in info:
                alert_lines.append(f"  - {days_left_phrase(item['days_left'])}: {item['detail']}")

        if alert_lines:
            message = t("expiry.title") + "\n\n" + "\n".join(alert_lines)
            for part in truncate_message(message):
                await self.bot.send_message(part)
            log.info(f"Expiry Guardian: sent alert with {len(items)} items")
        else:
            log.info("Expiry Guardian: no alerts needed")
