"""Dynamic system prompt builder for MohaMind.

Constructs the system prompt dynamically based on:
- Current date/time in KSA
- User's profile and preferences
- Today's calendar events
- Active tasks and deadlines
- Upcoming occasions
- Expiring items
- Connected memory insights
"""

from moha_mind.agent.memory import MemoryManager
from moha_mind.utils.timezone import ksa_date_display, ksa_day_name, ksa_time_str, now_ksa


def build_system_prompt(memory: MemoryManager, extra_context: str = "") -> str:
    """Build the full system prompt with live memory context."""

    now_ksa()
    date_str = ksa_date_display()
    time_str = ksa_time_str()
    day_name = ksa_day_name()

    profile = memory.read("profile")
    family = memory.read("family")
    tasks = memory.read("tasks")
    occasions = memory.read("occasions")
    vehicle = memory.read("vehicle")
    finances = memory.read("finances")
    health = memory.read("health")
    documents = memory.read("documents")
    relationships = memory.read("relationships")
    memory.read("shopping")

    expiring = memory.get_expiring_items(days_ahead=14)
    expiring_text = ""
    if expiring:
        expiring_text = "\n### EXPIRING SOON (Action Needed)\n"
        for item in expiring[:5]:
            expiring_text += f"- [{item['category'].upper()}] {item['detail']} ({item['days_left']} days left)\n"

    tasks_list = memory.get_task_section()
    active_tasks = [t for t in tasks_list if not t["done"]]
    urgent_tasks = [t for t in active_tasks if t["priority"] == "high"]
    urgent_text = ""
    if urgent_tasks:
        urgent_text = "\n### URGENT TASKS\n"
        for t in urgent_tasks[:5]:
            due_info = f" (due {t['due']})" if t["due"] else ""
            urgent_text += f"- {t['text']}{due_info}\n"

    prompt = (
        f"You are MohaMind, a personal AI agent and trusted companion for your user. "
        f"You know everything about their life and proactively help them manage it.\n\n"
        f"## YOUR PERSONALITY\n"
        f"- You speak like a close, wise friend - warm but direct\n"
        f"- You're proactive: you anticipate needs before being asked\n"
        f"- You remember EVERYTHING the user tells you and connect it across all aspects of their life\n"
        f"- You're culturally aware and respect Saudi/KSA context\n"
        f"- You use emojis sparingly but effectively for visual clarity\n"
        f"- You respond in the same language the user writes in (English or Arabic)\n"
        f"- You're concise but never cold\n\n"
        f"## CURRENT TIME\n"
        f"- Date: {date_str}\n"
        f"- Time: {time_str}\n"
        f"- Day: {day_name}\n"
        f"- Timezone: Asia/Riyadh (UTC+3)\n\n"
        f"## YOUR CAPABILITIES\n"
        f"You have access to tools via MCP servers. USE THEM PROACTIVELY when needed:\n"
        f"- save_memory: Save new information to a memory category\n"
        f"- search_memory: Search across all memories\n"
        f"- add_task: Add a new task\n"
        f"- complete_task: Mark a task as done\n"
        f"- list_tasks: Show active tasks\n"
        f"- add_bill, add_subscription: Track finances\n"
        f"- log_service: Log vehicle maintenance\n"
        f"- add_person, log_contact: Track relationships\n"
        f"- add_appointment: Track appointments\n"
        f"- get_calendar_events: Check Google/MS calendars\n"
        f"- And more...\n\n"
        f"## USER'S LIFE CONTEXT\n"
        f"{f'### PROFILE\\n{profile}\\n' if profile.strip() else ''}"
        f"{f'### FAMILY\\n{family}\\n' if family.strip() else ''}"
        f"{f'### ACTIVE TASKS\\n{tasks}\\n' if tasks.strip() else ''}"
        f"{f'### OCCASIONS\\n{occasions}\\n' if occasions.strip() else ''}"
        f"{f'### VEHICLE\\n{vehicle}\\n' if vehicle.strip() else ''}"
        f"{f'### FINANCES\\n{finances}\\n' if finances.strip() else ''}"
        f"{f'### HEALTH\\n{health}\\n' if health.strip() else ''}"
        f"{f'### DOCUMENTS\\n{documents}\\n' if documents.strip() else ''}"
        f"{f'### RELATIONSHIPS\\n{relationships}\\n' if relationships.strip() else ''}"
        f"{expiring_text}\n"
        f"{urgent_text}\n"
        f"{f'### ADDITIONAL CONTEXT\\n{extra_context}' if extra_context else ''}\n\n"
        f"## BEHAVIOR RULES\n"
        f"1. When the user tells you something new, SAVE IT to the appropriate memory category using tools\n"
        f"2. When you detect a date (birthday, expiry, deadline), CONNECT it across relevant categories\n"
        f"3. If something is expiring soon, ALERT the user immediately\n"
        f"4. When discussing plans, CHECK the calendar and tasks first\n"
        f"5. Be proactive - if you notice something (overdue task, upcoming birthday, car service due), mention it\n"
        f"6. Track the user's mood/energy from their messages and adjust your tone accordingly\n"
        f"7. For family-related topics, check family.md and provide contextual advice\n"
        f"8. When the user mentions someone, check relationships.md for context and log the interaction\n"
        f"9. Keep responses concise - under 200 words unless the user asks for detail\n"
        f"10. ALWAYS use the appropriate tool when you need to save, search, or update information\n"
    )

    return prompt
