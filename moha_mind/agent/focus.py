import asyncio
from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from moha_mind.agent.memory import MemoryManager
from moha_mind.utils.timezone import now_ksa

Energy = Literal["low", "neutral", "high"]


class FocusRequest(BaseModel):
    minutes: int = Field(default=60, ge=5, le=480, strict=True)
    energy: Energy = "neutral"


class FocusBlock(BaseModel):
    kind: Literal["task", "break"]
    title: str
    minutes: int
    reason: str
    due: str | None = None


class FocusReminder(BaseModel):
    title: str
    remind_at: str
    overdue: bool


class FocusPlan(BaseModel):
    generated_at: datetime
    energy: Energy
    budget_minutes: int
    planned_minutes: int
    active_tasks: int
    overdue_tasks: int
    remaining_tasks: int
    blocks: list[FocusBlock]
    reminders: list[FocusReminder]
    warnings: list[str]


class FocusPlanner:
    def __init__(self, memory: MemoryManager):
        self.memory = memory

    async def build(self, request: FocusRequest) -> FocusPlan:
        return await asyncio.to_thread(self._build, request)

    def _build(self, request: FocusRequest) -> FocusPlan:
        now = now_ksa()
        today = now.date()
        ranked = []
        overdue = 0
        warnings = []
        for index, task in enumerate(self.memory.get_task_section()):
            if task["done"]:
                continue
            due = None
            if task.get("due"):
                try:
                    due = date.fromisoformat(task["due"])
                except ValueError:
                    warnings.append(f"Invalid due date for {task['text'].strip()}; treated as undated.")
            days = (due - today).days if due else None
            priority = task.get("priority", "medium")
            if days is not None and days < 0:
                tier, reason = 0, f"Overdue by {abs(days)} day(s)"
                overdue += 1
            elif days == 0:
                tier, reason = 1, "Due today"
            elif days == 1:
                tier, reason = 2, "Due tomorrow"
            elif priority == "high":
                tier, reason = 3, "High priority"
            elif due:
                tier, reason = 4, f"Due in {days} day(s)"
            else:
                tier, reason = 5, "Make progress on your backlog"
            priority_rank = {"high": 0, "medium": 1, "low": 2}.get(priority, 1)
            ranked.append(((tier, due or date.max, priority_rank, index), task, reason, due))
        ranked.sort(key=lambda entry: entry[0])

        block_minutes, task_limit = {"low": (15, 1), "neutral": (25, 3), "high": (45, 5)}[request.energy]
        blocks = []
        remaining = request.minutes
        selected = 0
        for _, task, reason, due in ranked[:task_limit]:
            if selected:
                if remaining < 10:
                    break
                blocks.append(FocusBlock(kind="break", title="Take a break", minutes=5, reason="Step away and reset"))
                remaining -= 5
            duration = min(block_minutes, remaining)
            blocks.append(
                FocusBlock(
                    kind="task",
                    title=task["text"].strip(),
                    minutes=duration,
                    reason=reason,
                    due=due.isoformat() if due else None,
                )
            )
            remaining -= duration
            selected += 1

        reminders = []
        local_now = now.replace(tzinfo=None)
        for reminder in self.memory.get_reminder_section():
            try:
                when = datetime.strptime(reminder.get("remind_at", ""), "%Y-%m-%d %H:%M")
            except ValueError:
                warnings.append(f"Invalid reminder time for {reminder['text']}; check /reminders.")
                continue
            if when <= local_now + timedelta(hours=24):
                reminders.append(
                    FocusReminder(
                        title=reminder["text"],
                        remind_at=when.strftime("%Y-%m-%d %H:%M"),
                        overdue=when < local_now,
                    )
                )
        reminders.sort(key=lambda reminder: reminder.remind_at)
        return FocusPlan(
            generated_at=now,
            energy=request.energy,
            budget_minutes=request.minutes,
            planned_minutes=request.minutes - remaining,
            active_tasks=len(ranked),
            overdue_tasks=overdue,
            remaining_tasks=len(ranked) - selected,
            blocks=blocks,
            reminders=reminders,
            warnings=warnings,
        )

    async def get_focus_plan(self, minutes: int = 60, energy: Energy = "neutral") -> str:
        plan = await self.build(FocusRequest(minutes=minutes, energy=energy))
        return plan.model_dump_json(indent=2)
