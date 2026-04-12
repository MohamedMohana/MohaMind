# MohaMind

MohaMind is a CLI-first personal AI agent built for people who manage real life at high speed and do not want their tasks, reminders, family events, documents, subscriptions, and follow-ups scattered across apps.

It runs in the terminal, talks through Telegram, stores memory in readable Markdown files, and uses an OpenAI-compatible LLM stack with z.ai as the primary provider and OpenAI as fallback.

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-111827.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-382%20passing-16A34A.svg)](#testing)

## Why MohaMind

Most personal agents stop at chat. MohaMind is designed to act more like an operating layer for your life:

- CLI-first workflow with a branded command center instead of a thin prompt wrapper
- Telegram interface for natural back-and-forth in English or Arabic
- Markdown memory you can inspect, edit, back up, and version
- Proactive scheduler for briefings, reminders, expiry checks, and weekly reviews
- Attention Radar that ranks what needs action now
- Calendar integrations for Google Calendar and Microsoft Outlook

Typical use cases:

- "Tomorrow at 9 AM remind me to call Ahmad."
- "Remind me one day before my wedding anniversary and again on the same day."
- "What is coming up this week across tasks, bills, family events, and calendar?"
- "Who have I neglected lately?"

## Core Capabilities

### Personal memory

MohaMind stores persistent state in Markdown under `memory/`. The agent reads and updates files such as:

- `profile.md`
- `tasks.md`
- `reminders.md`
- `occasions.md`
- `family.md`
- `documents.md`
- `finances.md`
- `health.md`
- `relationships.md`
- `shopping.md`
- `vehicle.md`

This keeps the system understandable and portable. You are never locked into a database you cannot read.

### Proactive life operations

The scheduler runs recurring jobs for:

- Daily morning briefing
- Reminder checks every 30 minutes
- Expiry monitoring for documents and subscriptions
- Weekly review
- Social pulse nudges
- Family milestone updates

### Attention Radar

Attention Radar is a ranked view of what matters most across:

- overdue or upcoming tasks
- timed reminders
- expiring items
- birthdays, anniversaries, and other occasions
- family events
- neglected relationships

### Interfaces

MohaMind currently ships with:

- a rich interactive CLI
- a Telegram bot
- optional Google Calendar integration
- optional Microsoft Outlook / Graph integration

## Quick Start

### Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- at least one LLM API key:
  - [z.ai](https://open.bigmodel.cn)
  - [OpenAI](https://platform.openai.com/)

### Install

```bash
git clone https://github.com/MohamedMohana/MohaMind.git
cd MohaMind
uv sync
```

### Configure

The recommended path is the built-in setup wizard:

```bash
uv run mohamind setup
```

You can also use the lightweight first-run onboarding by simply launching `mohamind` with no API key configured. MohaMind will prompt for the provider, key, and timezone, then write `.env` for you.

### Run

```bash
# Interactive CLI
uv run mohamind

# Start with an initial message
uv run mohamind "Plan my week"

# One-shot mode
uv run mohamind -p "What is expiring soon?"

# Telegram bot only
uv run mohamind --bot

# CLI and Telegram together
uv run mohamind --all

# Configuration doctor
uv run mohamind doctor
```

## How To Use It Well

### 1. Treat it like a personal operations desk

Use MohaMind for actions with memory and follow-through:

- task capture
- reminders with explicit time
- birthdays and anniversaries
- subscriptions and documents
- family appointments
- relationship follow-ups

### 2. Be explicit with dates and people

Good prompts:

- `Tomorrow at 9 AM remind me to call Ahmad about the contract.`
- `Add a yearly reminder for Sara's birthday on August 18.`
- `What needs my attention this week?`
- `Search for all notes about my passport renewal.`

Arabic also works well for natural requests, for example:

- `ذكرني بكرة الساعة 9 الصباح أتصل بأحمد`
- `ذكرني قبل عيد زواجي بيوم وفي نفس اليوم`

### 3. Use the command surfaces directly

Chat is useful, but the CLI and Telegram commands expose the fastest paths for daily usage.

## CLI Guide

MohaMind's terminal interface is built around a branded command center called the Majlis. It is meant to feel like an operator console, not a plain chatbot shell.

### Main CLI commands

| Command | What it does |
| --- | --- |
| `/majlis` | Open the command center view |
| `/radar` | Show ranked attention radar |
| `/calendar` | Show calendar integration snapshot |
| `/today` | Show today's overview |
| `/tasks` | List active tasks |
| `/reminders` | List scheduled reminders |
| `/remind <text>` | Create a timed reminder from natural language |
| `/briefing` | Generate the daily briefing |
| `/review` | Generate the weekly review |
| `/expiring` | Show upcoming expiries |
| `/family` | Show family-related upcoming items |
| `/social` | Show social follow-ups and neglected contacts |
| `/finance` | Show bills and subscription-related information |
| `/health` | Show health-related information |
| `/vehicle` | Show vehicle-related information |
| `/search <query>` | Search all memory files |
| `/memory` | Preview memory categories |
| `/add task <text>` | Quick-add a task |
| `/done <text>` | Mark a task complete |
| `/note <title>` | Save or list notes |
| `/provider zai|openai` | Switch provider live |
| `/model <name>` | Change the active model live |
| `/doctor` | Run configuration checks |
| `/config` | Show current configuration |

### CLI examples

```text
/majlis
/radar
/remind remind me tomorrow at 9 am to call the school
/search passport
/add task renew car insurance
```

## Telegram Guide

Telegram is the conversational interface for day-to-day capture and reminders. You can use commands or just send free-form messages.

### Telegram commands

| Command | What it does |
| --- | --- |
| `/start` | Show the intro and available workflows |
| `/today` | Show today's overview |
| `/tomorrow` | Show tomorrow's overview |
| `/tasks` | Show active tasks |
| `/reminders` | Show reminder queue |
| `/remind <text>` | Create a timed reminder |
| `/add <task>` | Add a task |
| `/done <task>` | Complete a task |
| `/briefing` | Generate the briefing |
| `/review` | Generate the weekly review |
| `/calendar` | Show upcoming calendar events |
| `/family` | Show family overview |
| `/social` | Show social overview |
| `/health` | Show health information |
| `/pay` | Show finance information |
| `/car` | Show vehicle information |
| `/expiry` | Show expiring items |
| `/shopping` | Show shopping information |
| `/remember <text>` | Save something to memory |
| `/recall <query>` | Search memory |
| `/forget <query>` | Request forgetting / removal flow |
| `/note <title>` | Save a note |
| `/week` | Show the weekly outlook |
| `/radar` | Show attention radar |

### Telegram examples

```text
/remind remind me next Thursday at 4 pm to call the clinic
/radar
/today
```

Or just talk naturally:

```text
I have a meeting tomorrow at 9 AM, remind me 30 minutes before.
My son's birthday is on 2026-06-20. Save it as an occasion and remind me before it.
```

## Integrations

### LLM providers

- `z.ai` is the primary default
- `OpenAI` is supported as fallback or primary
- provider switching is available from the CLI

### Telegram

MohaMind can run as a headless Telegram bot or together with the CLI.

Required environment variables:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

### Google Calendar

1. Create OAuth credentials in Google Cloud.
2. Enable the Google Calendar API.
3. Place the credentials file at `./credentials/google_credentials.json`, or update the path in `.env`.

Relevant variables:

- `GOOGLE_CREDENTIALS_PATH`
- `GOOGLE_TOKEN_PATH`

### Microsoft Outlook / Graph

1. Register an app in Azure.
2. Grant calendar read permissions.
3. Place the client credentials in `.env`.

Relevant variables:

- `MS_CLIENT_ID`
- `MS_CLIENT_SECRET`
- `MS_TENANT_ID`
- `MS_TOKEN_PATH`

## Configuration

MohaMind reads configuration from `.env` using Pydantic Settings.

Important variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `PRIMARY_LLM` | `zai` | Active provider |
| `FALLBACK_LLM` | `openai` | Fallback provider |
| `ZAI_API_KEY` | empty | z.ai API key |
| `ZAI_MODEL` | `glm-4-plus` | z.ai model |
| `OPENAI_API_KEY` | empty | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model |
| `TIMEZONE` | `Asia/Riyadh` | Agent timezone |
| `MORNING_BRIEFING_TIME` | `08:00` | Daily briefing time |
| `WEEKLY_REVIEW_DAY` | `sun` | Weekly review day |
| `WEEKLY_REVIEW_TIME` | `19:00` | Weekly review time |
| `MEMORY_DIR` | `./memory` | Markdown memory directory |
| `LOG_LEVEL` | `INFO` | Logging level |

Use `.env.example` as the reference template.

## Memory Model

MohaMind's core design choice is simple: your personal data remains legible.

The memory system uses:

- Markdown files with `##` sections
- daily logs stored under `memory/daily_log/`
- notes stored under `memory/notes/`
- dedicated files for tasks, reminders, occasions, relationships, finance, and more

Benefits:

- easy to audit
- easy to back up
- easy to edit manually
- works well for open source and self-hosted usage

## Architecture

```text
MohaMind/
├── moha_mind/
│   ├── agent/           core agent loop, memory, prompting
│   ├── cli/             interactive terminal interface
│   ├── mcp_servers/     task, memory, family, social, reminders, attention
│   ├── scheduler/       briefings, reminders, weekly review, expiry checks
│   ├── telegram_bot/    Telegram handlers and formatting
│   ├── utils/           dates, timezone helpers, occasion parsing
│   ├── config.py        environment settings
│   └── main.py          bootstrap and runtime modes
├── memory/              personal memory files
├── credentials/         OAuth tokens and API credentials
└── tests/               test suite
```

High-level runtime flow:

1. Bootstrap memory, agent, and MCP-style tool servers.
2. Register tools for tasks, family, reminders, social tracking, calendars, and attention radar.
3. Run through the CLI, Telegram, or both.
4. Let the scheduler handle proactive jobs in the background.

## Development

### Install dependencies

```bash
uv sync
```

### Run tests

```bash
uv run pytest -q
```

### Lint

```bash
uv run ruff check .
uv run ruff format .
```

## Testing

The current test suite covers the core agent, memory manager, CLI, scheduler behavior, attention radar, reminders, and occasion parsing.

```bash
uv run pytest -q
```

At the time of writing, the suite passes with `382` tests.

## Product Direction

MohaMind is aimed at becoming a serious personal agent for operators, founders, and busy family people who need:

- strong capture
- reliable reminders
- proactive life organization
- direct control over memory
- multi-surface access from terminal and Telegram

The codebase is already structured for further work such as better reminder parsing, voice-note intake, deeper calendar automation, and more advanced context management.

## License

MIT. See [LICENSE](LICENSE).
