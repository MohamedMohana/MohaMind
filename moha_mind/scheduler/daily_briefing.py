"""Daily morning briefing generator."""

from moha_mind.agent.core import MohaMindAgent
from moha_mind.agent.memory import MemoryManager
from moha_mind.telegram_bot.bot import MohaMindBot
from moha_mind.telegram_bot.formatters import truncate_message
from moha_mind.utils.logging_config import log
from moha_mind.utils.timezone import ksa_date_display, ksa_date_display_ar


class DailyBriefing:
    def __init__(self, agent: MohaMindAgent, memory: MemoryManager, bot: MohaMindBot):
        self.agent = agent
        self.memory = memory
        self.bot = bot

    async def generate_and_send(self) -> None:
        """Generate the morning briefing and send it via Telegram."""
        log.info("Generating morning briefing...")

        try:
            briefing = await self.agent.generate_briefing()

            header = f"🌅 صباح الخير. {ksa_date_display_ar()}\n\n"
            full_message = header + briefing

            for part in truncate_message(full_message):
                await self.bot.send_message(part)

            self.memory.save_daily_log(f"Morning briefing sent: {ksa_date_display()}")
            log.info("Morning briefing sent successfully")

        except Exception as e:
            log.error(f"Morning briefing failed: {e}")
            try:
                await self.bot.send_message(
                    "صباح الخير. واجهت مشكلة أثناء إعداد الملخص الكامل اليوم. اكتب لي وسأعطيك ملخصًا سريعًا."
                )
            except Exception:
                pass
