"""Scheduler job registry - configures all APScheduler jobs."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from moha_mind.agent.core import MohaMindAgent
from moha_mind.agent.memory import MemoryManager
from moha_mind.config import settings
from moha_mind.scheduler.daily_briefing import DailyBriefing
from moha_mind.scheduler.expiry_guardian import ExpiryGuardian
from moha_mind.scheduler.memory_consolidator import MemoryConsolidator
from moha_mind.scheduler.reliability_guardian import ReliabilityGuardian
from moha_mind.scheduler.reminder_engine import ReminderEngine
from moha_mind.scheduler.social_pulse import SocialPulse
from moha_mind.scheduler.weekly_review import WeeklyReview
from moha_mind.telegram_bot.bot import MohaMindBot
from moha_mind.utils.i18n import t
from moha_mind.utils.logging_config import log


def parse_time(time_str: str) -> tuple[int, int]:
    """Parse HH:MM time string."""
    parts = time_str.split(":")
    return int(parts[0]), int(parts[1])


class SchedulerJobs:
    def __init__(
        self,
        agent: MohaMindAgent,
        memory: MemoryManager,
        bot: MohaMindBot,
    ):
        self.agent = agent
        self.memory = memory
        self.bot = bot
        self.scheduler = AsyncIOScheduler(timezone=settings.timezone)

        self.briefing = DailyBriefing(agent, memory, bot)
        self.weekly_review = WeeklyReview(agent, memory, bot)
        self.expiry_guardian = ExpiryGuardian(memory, bot)
        self.social_pulse = SocialPulse(memory, bot)
        self.reminder_engine = ReminderEngine(memory, bot)
        self.memory_consolidator = MemoryConsolidator(agent, memory, bot)
        self.reliability_guardian = ReliabilityGuardian(memory, bot, summarizer=agent.summarizer)

    def setup(self) -> None:
        """Register all scheduled jobs."""
        tz = settings.timezone

        hour, minute = parse_time(settings.morning_briefing_time)
        self.scheduler.add_job(
            self.briefing.generate_and_send,
            CronTrigger(hour=hour, minute=minute, timezone=tz),
            id="daily_briefing",
            name="Morning Briefing",
            replace_existing=True,
        )
        log.info(f"Scheduled: Morning Briefing at {hour:02d}:{minute:02d} {tz}")

        self.scheduler.add_job(
            self.expiry_guardian.check_and_alert,
            CronTrigger(hour=(hour + 1) % 24, minute=0, timezone=tz),
            id="expiry_guardian",
            name="Expiry Guardian",
            replace_existing=True,
        )
        log.info(f"Scheduled: Expiry Guardian at {(hour + 1) % 24:02d}:00 {tz}")

        self.scheduler.add_job(
            self.reminder_engine.check_and_remind,
            IntervalTrigger(minutes=30),
            id="reminder_engine",
            name="Reminder Engine",
            replace_existing=True,
        )
        log.info("Scheduled: Reminder Engine every 30 minutes")

        review_hour, review_minute = parse_time(settings.weekly_review_time)
        day_map = {
            "mon": "mon",
            "tue": "tue",
            "wed": "wed",
            "thu": "thu",
            "fri": "fri",
            "sat": "sat",
            "sun": "sun",
        }
        day_of_week = day_map.get(settings.weekly_review_day.lower(), "sun")
        self.scheduler.add_job(
            self.weekly_review.generate_and_send,
            CronTrigger(
                day_of_week=day_of_week,
                hour=review_hour,
                minute=review_minute,
                timezone=tz,
            ),
            id="weekly_review",
            name="Weekly Life Review",
            replace_existing=True,
        )
        log.info(f"Scheduled: Weekly Review on {day_of_week} at {review_hour:02d}:{review_minute:02d} {tz}")

        self.scheduler.add_job(
            self.social_pulse.check_and_nudge,
            CronTrigger(day_of_week="mon", hour=18, minute=0, timezone=tz),
            id="social_pulse",
            name="Social Pulse",
            replace_existing=True,
        )
        log.info("Scheduled: Social Pulse on Mondays at 18:00")

        self.scheduler.add_job(
            self._pregnancy_update_check,
            CronTrigger(day_of_week="sat", hour=9, minute=0, timezone=tz),
            id="pregnancy_update",
            name="Pregnancy Week Update",
            replace_existing=True,
        )
        log.info("Scheduled: Pregnancy Update on Saturdays at 09:00")

        if getattr(settings, "consolidator_enabled", False):
            cons_hour, cons_minute = parse_time(getattr(settings, "consolidator_time", "02:30"))
            self.scheduler.add_job(
                self.memory_consolidator.run,
                CronTrigger(hour=cons_hour, minute=cons_minute, timezone=tz),
                id="memory_consolidator",
                name="Memory Consolidator",
                replace_existing=True,
            )
            log.info(f"Scheduled: Memory Consolidator at {cons_hour:02d}:{cons_minute:02d} {tz}")

        if getattr(settings, "reliability_guardian_enabled", True):
            rel_hour, rel_minute = parse_time(getattr(settings, "reliability_guardian_time", "03:10"))
            self.scheduler.add_job(
                self.reliability_guardian.run,
                CronTrigger(hour=rel_hour, minute=rel_minute, timezone=tz),
                id="reliability_guardian",
                name="Reliability Guardian",
                replace_existing=True,
            )
            log.info(f"Scheduled: Reliability Guardian at {rel_hour:02d}:{rel_minute:02d} {tz}")

        self.scheduler.add_job(
            self._monthly_subscription_check,
            CronTrigger(day=1, hour=10, minute=0, timezone=tz),
            id="subscription_check",
            name="Monthly Subscription Check",
            replace_existing=True,
        )
        log.info("Scheduled: Subscription Check on 1st of each month at 10:00")

    async def _pregnancy_update_check(self) -> None:
        """Weekly pregnancy milestone check."""
        from moha_mind.mcp_servers.family.server import FamilyServer

        family_server = FamilyServer(self.memory)
        result = await family_server.handle_tool("family_update_pregnancy_week", {})
        if result and "week" in result.lower():
            await self.bot.send_message(f"{t('jobs.pregnancy_header')}\n{result}")

    async def _monthly_subscription_check(self) -> None:
        """Monthly subscription review."""
        response = await self.agent.chat(
            t("jobs.subscription_prompt"),
            chat_id="scheduler",
        )
        from moha_mind.telegram_bot.formatters import truncate_message

        header = t("jobs.subscription_header") + "\n\n"
        for part in truncate_message(header + response):
            await self.bot.send_message(part)

    def start(self) -> None:
        """Start the scheduler."""
        self.setup()
        self.scheduler.start()
        log.info("Scheduler started with all jobs")

    def stop(self) -> None:
        """Stop the scheduler."""
        self.scheduler.shutdown(wait=False)
        log.info("Scheduler stopped")
