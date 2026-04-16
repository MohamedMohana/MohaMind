"""Weekly life review generator."""

from moha_mind.agent.core import MohaMindAgent
from moha_mind.agent.memory import MemoryManager
from moha_mind.telegram_bot.bot import MohaMindBot
from moha_mind.telegram_bot.formatters import truncate_message
from moha_mind.utils.logging_config import log
from moha_mind.utils.timezone import ksa_today_str


class WeeklyReview:
    def __init__(self, agent: MohaMindAgent, memory: MemoryManager, bot: MohaMindBot):
        self.agent = agent
        self.memory = memory
        self.bot = bot

    async def generate_and_send(self) -> None:
        """Generate the weekly review and send via Telegram."""
        log.info("Generating weekly life review...")

        try:
            review = await self.agent.generate_weekly_review()

            header = "📊 المراجعة الأسبوعية\n\n"
            full_message = header + review

            for part in truncate_message(full_message):
                await self.bot.send_message(part)

            self.memory.save_daily_log(f"Weekly review sent: {ksa_today_str()}")
            log.info("Weekly review sent successfully")

        except Exception as e:
            log.error(f"Weekly review failed: {e}")
