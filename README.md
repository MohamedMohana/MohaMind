<div align="center">

# 🧠 MohaMind

**Your Personal AI Agent That Knows Everything About You**

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests: 345](https://img.shields.io/badge/tests-345%20passing-brightgreen.svg)]()

*Connects to Telegram, Google Calendar, Outlook, and manages your entire life — tasks, family, finances, health, relationships, vehicle, documents, and more.*

[Getting Started](#-getting-started) • [Features](#-features) • [Architecture](#-architecture) • [Commands](#-commands) • [Configuration](#-configuration)

</div>

---

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager (recommended) or pip
- An API key from [z.ai](https://open.bigmodel.cn) (free tier available) or [OpenAI](https://platform.openai.com)

### Install

```bash
# Clone the repo
git clone https://github.com/MohamedMohana/MohaMind.git
cd MohaMind

# Install dependencies
uv sync

# Run the setup wizard (guides you through API keys, timezone, etc.)
uv run mohamind setup
```

The setup wizard will:
1. Ask which LLM provider to use (z.ai or OpenAI)
2. Prompt for your API key (hidden input)
3. Optionally configure Telegram bot integration
4. Set your timezone and briefing schedule
5. Save everything to `.env` (never committed to git)

### Run

```bash
# Start MohaMind (opens interactive CLI - the default)
uv run mohamind

# Start with an initial message
uv run mohamind "What tasks are due this week?"

# One-shot mode (print answer, exit)
uv run mohamind -p "Summarize my upcoming expirations"

# Start Telegram bot daemon (headless, no CLI)
uv run mohamind --bot

# CLI + Telegram bot together
uv run mohamind --all

# Check your configuration
uv run mohamind doctor

# Re-run setup wizard
uv run mohamind setup
```

### First-Run Experience

When you first run `mohamind`, it detects no API key and shows a quick inline auth dialog:

```
╭──────────────────────────────────────────────╮
│  Welcome to MohaMind!                        │
│                                              │
│  No API key found. Let's get you set up.     │
│  Your key is saved to .env (never committed).│
╰──────────────────────────────────────────────╯

  Choose your AI provider:
  1 z.ai (GLM-4) - recommended
  2 OpenAI (GPT)
  Choice [1]: 1

  Get your key from https://open.bigmodel.cn
  z.ai API key: sk-xxxxx

  Your timezone [Asia/Riyadh]:

  ✅ Saved! You're ready to go.

  Configure Telegram bot? (optional) [y/N]:
```

No manual config editing. Just run `mohamind` and go.

---

## ✨ Features

### 🧠 Smart AI Agent
- **z.ai GLM-4** as primary brain (cost-effective, powerful)
- **OpenAI GPT-4o-mini** as automatic fallback
- Tool-calling loop with up to 5 rounds of tool usage per conversation
- Context-aware with full memory access in every conversation

### 💾 Connected Memory Engine
- Human-readable **Markdown files** for all your data
- 14 memory categories: profile, family, tasks, occasions, vehicle, finances, health, home, documents, travel, learning, shopping, relationships, energy log
- **Auto-linking engine** — mentions "birthday" in a task? Automatically connects to family/occasions
- Search across all memories instantly

### ⏰ Proactive Scheduling
- **Morning Briefing** — daily at your chosen time (default 8:00 AM KSA)
- **Expiry Guardian** — tracks everything expiring (passport, insurance, subscriptions) and alerts at 90/30/7/0 days
- **Social Pulse** — nudges you to reconnect with people you haven't contacted
- **Reminder Engine** — checks every 30 minutes for upcoming deadlines
- **Weekly Life Review** — comprehensive Sunday review of your week
- **Pregnancy Tracker** — weekly milestone updates (Saturdays at 9 AM)

### 📱 Telegram Bot Interface
- 20+ commands: `/briefing`, `/tasks`, `/add`, `/search`, `/family`, `/social`, `/forget`, etc.
- Rich formatted messages with priority colors and urgency indicators
- Full conversation support — just talk naturally

### 🖥️ Premium CLI Interface
- **Neural pulse spinner** — animated brain-wave thinking indicator
- **Mood-aware themes** — colors adapt based on your energy state
- **Rich panels** — beautiful tables for tasks, briefings, memory search
- **Slash commands** with autocomplete and persistent history
- **prompt_toolkit** powered input with history navigation

### 🏠 Life Management

| Category | Features |
|----------|----------|
| **Tasks** | Add, complete, update, list with priorities and due dates |
| **Family** | Pregnancy tracker, kid events, vaccination schedule, appointments |
| **Vehicle** | Service history, mileage tracking, next service reminders |
| **Finances** | Bills, subscriptions, upcoming payment alerts |
| **Health** | Medications, vitals logging, doctor directory |
| **Home** | Maintenance log, appliance warranties |
| **Documents** | Passport, ID, visa, driver license expiry tracking |
| **Social** | Relationship tracker, contact frequency, gift ideas, birthday alerts |
| **Learning** | Course tracking, progress updates |
| **Shopping** | Shopping lists and purchase tracking |

### 📅 Calendar Integration
- **Google Calendar** — view upcoming events
- **Microsoft Outlook** — view calendar events via Microsoft Graph

---

## 🏗 Architecture

```
MohaMind/
├── moha_mind/
│   ├── agent/              # Core AI agent
│   │   ├── core.py         # LLM conversation loop with tool calling
│   │   ├── memory.py       # Markdown memory manager
│   │   ├── connected_memory.py  # Auto-linking engine
│   │   ├── energy_tracker.py    # Mood/energy pattern learning
│   │   └── system_prompt.py     # Dynamic prompt builder
│   ├── cli/                # Premium terminal interface
│   │   ├── app.py          # Main CLI loop with slash commands
│   │   ├── setup_wizard.py # Interactive setup & doctor
│   │   ├── spinner.py      # Neural pulse animation
│   │   ├── themes.py       # Mood-aware color schemes
│   │   ├── banner.py       # Startup banner with stats
│   │   ├── display.py      # Rich output panels
│   │   ├── input_handler.py # prompt_toolkit with autocomplete
│   │   └── commands.py     # Slash command registry
│   ├── mcp_servers/        # MCP tool servers
│   │   ├── memory_store/   # Memory CRUD
│   │   ├── tasks/          # Task management
│   │   ├── life_tracker/   # Vehicle, finance, health, home, docs, learning
│   │   ├── family/         # Pregnancy, kids, vaccinations
│   │   ├── social/         # Relationships, gifts, social pulse
│   │   ├── google_calendar/ # Google Calendar API
│   │   └── microsoft_graph/ # Outlook + MS Calendar
│   ├── scheduler/          # APScheduler jobs
│   ├── telegram_bot/       # Telegram interface
│   ├── utils/              # Shared utilities
│   ├── config.py           # Pydantic settings from .env
│   └── main.py             # Entry point with setup/doctor/CLI modes
├── memory/                 # Your personal data (gitignored)
├── credentials/            # OAuth tokens (gitignored)
├── tests/                  # 345 tests
├── .env                    # Your secrets (gitignored, created by setup)
└── .env.example            # Template with all options documented
```

---

## 💻 Commands

### CLI Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all available commands |
| `/today` | Today's overview (tasks, expiring, time) |
| `/tasks` | Show active tasks |
| `/done <text>` | Complete a task |
| `/add task <text>` | Quick add a task |
| `/add note <title>` | Quick save a note |
| `/note <title>` | Save or list notes |
| `/briefing` | Generate morning briefing |
| `/review` | Generate weekly life review |
| `/expiring` | Show expiring items (optional: days) |
| `/search <query>` | Search across all memories |
| `/memory` | Show all memory categories with preview |
| `/family` | Family: upcoming events |
| `/social` | Social: neglected contacts & birthdays |
| `/vehicle` | Vehicle info |
| `/health` | Health: medications & vitals |
| `/finance` | Finance: upcoming bills & subscriptions |
| `/mood` | Show energy/mood analysis |
| `/stats` | Show system stats |
| `/config` | Show current configuration |
| `/setup` | Re-run setup wizard |
| `/doctor` | Check configuration health |
| `/provider zai\|openai` | Switch LLM provider (live, no restart) |
| `/model <name>` | Change model (live, no restart) |
| `/key` | Update API key for current provider |
| `/clear` | Clear screen |
| `/quit` | Exit MohaMind |

### Terminal Commands

```bash
mohamind                # Interactive CLI (default)
mohamind "query"        # Start with initial message
mohamind -p "query"     # One-shot: print answer and exit
mohamind --bot          # Telegram bot daemon (headless)
mohamind --all          # CLI + Telegram bot together
mohamind setup          # Interactive setup wizard
mohamind setup --quick  # Quick setup (only required fields)
mohamind doctor         # Check configuration health
```

### Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/briefing` | Morning briefing |
| `/today` | Today's schedule and tasks |
| `/tomorrow` | Tomorrow's schedule |
| `/tasks` | Active tasks |
| `/add <task>` | Add a task |
| `/done <task>` | Complete a task |
| `/search <query>` | Search memories |
| `/family` | Family overview |
| `/social` | Social connections |
| `/vehicle` | Vehicle info |
| `/finance` | Finance overview |
| `/health` | Health info |
| `/expire` | Expiring items |
| `/forget <query>` | Remove from memory |
| `/help` | Show all commands |

---

## ⚙️ Configuration

All configuration is stored in `.env` (created by `mohamind setup`). Key options:

| Variable | Default | Description |
|----------|---------|-------------|
| `PRIMARY_LLM` | `zai` | Main AI brain (`zai` or `openai`) |
| `ZAI_API_KEY` | — | z.ai API key from [open.bigmodel.cn](https://open.bigmodel.cn) |
| `OPENAI_API_KEY` | — | OpenAI API key (fallback) |
| `FALLBACK_LLM` | `openai` | Fallback if primary fails (`zai`, `openai`, or `none`) |
| `TELEGRAM_BOT_TOKEN` | — | From @BotFather (optional for CLI mode) |
| `TELEGRAM_CHAT_ID` | — | From @userinfobot (optional for CLI mode) |
| `TIMEZONE` | `Asia/Riyadh` | Your IANA timezone |
| `MORNING_BRIEFING_TIME` | `08:00` | Daily briefing time (HH:MM) |
| `WEEKLY_REVIEW_DAY` | `sun` | Weekly review day |
| `WEEKLY_REVIEW_TIME` | `19:00` | Weekly review time |
| `MEMORY_DIR` | `./memory` | Memory files directory |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

### Calendar Integration (Optional)

**Google Calendar:**
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Enable Google Calendar API
3. Create OAuth credentials
4. Save to `credentials/google_credentials.json`

**Microsoft Outlook:**
1. Register an app in [Azure Portal](https://portal.azure.com)
2. Grant `Calendars.Read` permission
3. Set `MS_CLIENT_ID`, `MS_CLIENT_SECRET` in `.env`

---

## 🧪 Testing

```bash
# Run all 345 tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_cli.py

# Lint check
uv run ruff check .

# Format check
uv run ruff format --check .
```

---

## 🗺️ Roadmap

- [ ] MCP Memory knowledge graph integration
- [ ] Smart Day Planning with energy-aware scheduling
- [ ] Monthly financial summary with charts
- [ ] Multi-user support
- [ ] Voice messages via Telegram
- [ ] Web dashboard
- [ ] Docker deployment for VPS
- [ ] Plugin system for custom MCP servers

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built with 🧠 by [Mohamed Mohana](https://github.com/MohamedMohana)

*Your life, organized by AI.*

</div>
