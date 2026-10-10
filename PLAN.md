# MohaMind - Development Plan

## Project Status: v0.3.0 - WhatsApp Self-Chat, Easier Onboarding, and Bounded Tool Execution

### Architecture Overview

```
MohaMind/
├── moha_mind/                    # Main package
│   ├── main.py                   # Entry point - starts bot + scheduler + MCP
│   ├── config.py                 # Pydantic settings from .env
│   ├── agent/                    # Brain of the agent
│   │   ├── core.py               # LLM conversation loop (z.ai + OpenAI fallback)
│   │   ├── system_prompt.py      # Dynamic prompt builder with memory context
│   │   ├── memory.py             # Memory manager (MD files)
│   │   ├── connected_memory.py   # Cross-category memory linking engine
│   │   └── energy_tracker.py     # Mood/energy pattern learning
│   ├── mcp_servers/              # Tool servers (MCP protocol)
│   │   ├── memory_store/         # Memory CRUD operations
│   │   ├── tasks/                # Task management
│   │   ├── life_tracker/         # Vehicle, finance, health, home, docs
│   │   ├── family/               # Pregnancy, kids, school
│   │   ├── social/               # Relationships, gifts, social pulse
│   │   ├── google_calendar/      # Google Calendar API
│   │   └── microsoft_graph/      # Outlook + MS Calendar
│   ├── telegram_bot/             # Telegram interface
│   │   ├── bot.py                # Bot setup & lifecycle
│   │   ├── handlers.py           # Command & message handlers
│   │   └── formatters.py         # Message formatting
│   ├── scheduler/                # Proactive intelligence
│   │   ├── jobs.py               # APScheduler job registry
│   │   ├── daily_briefing.py     # 8 AM KSA morning briefing
│   │   ├── weekly_review.py      # Sunday life review
│   │   ├── expiry_guardian.py    # Expiry date tracking
│   │   ├── social_pulse.py       # Relationship maintenance
│   │   └── reminder_engine.py    # Task/event reminders
│   └── utils/                    # Utilities
│       ├── timezone.py           # KSA (Asia/Riyadh) timezone
│       ├── date_helpers.py       # Date parsing & helpers
│       └── logging_config.py     # Rich logging
├── memory/                       # Persistent memory (human-readable MD)
├── credentials/                  # OAuth tokens (gitignored)
└── tests/                        # Test suite
```

### Unique Features

1. **Connected Memory** - Auto-links info across all categories
2. **Expiry Guardian** - Proactive expiry tracking (90/30/7/0 day alerts)
3. **Smart Day Planning** - Energy-based task scheduling
4. **Social Pulse** - Relationship maintenance nudges
5. **Weekly Life Review** - Comprehensive week summary
6. **Family Mode** - Pregnancy tracker, kids, vaccinations

### Life Categories Covered

- Tasks & To-dos
- Google Calendar + Microsoft Calendar
- Vehicle (service, insurance, registration)
- Finances (bills, subscriptions, salary)
- Health (medications, doctors, gym)
- Family (pregnancy, kids, school)
- Relationships (friends, family, gifts)
- Home (rent, utilities, maintenance)
- Documents (passport, ID, license, visa)
- Travel (trips, visa requirements)
- Learning (courses, books, certifications)
- Shopping (lists, sizes, brands)

### Setup Instructions

1. Copy `.env.example` to `.env` and fill in API keys
2. `uv sync` to install dependencies
3. `uv run mohamind` to start

### API Keys Needed

- **z.ai (Zhipu)**: Get from https://open.bigmodel.cn
- **Telegram Bot**: Create via @BotFather on Telegram
- **Google Calendar** (optional): Set up OAuth at https://console.cloud.google.com
- **Microsoft Graph** (optional): Register app at https://portal.azure.com

### Scheduled Jobs

| Job | Schedule | Purpose |
|---|---|---|
| Morning Briefing | Daily 8:00 AM KSA | Full day plan |
| Expiry Guardian | Daily 9:00 AM KSA | Expiry alerts |
| Reminder Engine | Every 30 min | Task/event reminders |
| Social Pulse | Monday 6:00 PM | Relationship nudges |
| Weekly Review | Sunday 7:00 PM | Week summary |
| Pregnancy Update | Saturday 9:00 AM | Weekly milestone |
| Subscription Check | 1st monthly 10:00 AM | Monthly review |
