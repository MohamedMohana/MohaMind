# MohaMind

MohaMind is a CLI-first personal AI agent for real life operations: reminders, tasks, family events, appointments, bills, subscriptions, documents, health, vehicle upkeep, and follow-up.

It is built for people who want:

- a terminal-first workflow
- readable memory files instead of opaque databases
- reliable reminders in KSA time
- Arabic and English conversation
- support for normal spoken Arabic and Gulf/Saudi dialect
- Telegram access in addition to the local CLI

MohaMind uses z.ai (GLM) by default and can fall back to OpenAI.

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-111827.svg)](LICENSE)

## What It Does

MohaMind combines four layers into one personal agent:

- `Conversation`: interactive CLI and Telegram chat
- `Structured memory`: persistent Markdown files under `memory/`
- `Session recall`: persistent conversation history in `memory/sessions.db`
- `Proactive jobs`: scheduled checks for reminders, expiries, briefings, and reviews

In practice, that means you can talk to it normally, let it store what matters, and ask it later what is due, what is expiring, or what was discussed before.

## Core Capabilities

- Natural-language reminders with exact KSA scheduling
- Task tracking with priority and due dates
- Occasion tracking for birthdays, anniversaries, and recurring annual dates
- Finance tracking for bills and subscriptions
- Vehicle, health, family, and document tracking
- Persistent conversation recall across restarts
- Attention radar for prioritizing what matters now
- Daily briefing and weekly review
- Arabic and English responses
- Colloquial Arabic understanding, including phrases like:
  - `بكره`
  - `بعد بكره`
  - `٤ العصر`
  - `٥ الصبح`
  - `يوم نعم ويوم لا`

## Quick Start

### Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- one API key:
  - [z.ai](https://open.bigmodel.cn)
  - [OpenAI](https://platform.openai.com/)

You do not need Telegram, Google Calendar, or Outlook to get started.

### Install

```bash
git clone https://github.com/MohamedMohana/MohaMind.git
cd MohaMind
uv sync
```

### Configure

```bash
uv run mohamind setup
```

The setup wizard writes `.env` and asks for:

- your LLM provider
- your API key
- your timezone
- optional Telegram settings

If you skip setup and run `uv run mohamind` without an API key, MohaMind starts a first-run onboarding flow and writes `.env` for you.

### Run

```bash
uv run mohamind
```

Other useful entry points:

```bash
uv run mohamind "Plan my week"
uv run mohamind -p "What needs my attention today?"
uv run mohamind --help
uv run mohamind doctor
uv run mohamind --bot
uv run mohamind --all
```

## Run Modes

MohaMind supports these main run modes:

- `uv run mohamind`
  Opens the interactive CLI.

- `uv run mohamind --bot`
  Runs Telegram only.

- `uv run mohamind --all`
  Runs the CLI and Telegram together.

- `uv run mohamind -p "..."`  
  One-shot mode for shell usage and quick queries.

Important:

- the CLI is your main control surface
- Telegram is the main push-notification surface
- scheduled reminders and proactive alerts are most useful when `--bot` or `--all` is running

## First 5 Minutes

Start the CLI:

```bash
uv run mohamind
```

Then try these commands:

```text
/majlis
/today
/add task renew passport
/remind remind me tomorrow at 9 am to call Ahmad
/recall passport
/search passport
/memory
```

You can also just talk naturally:

```text
Tomorrow at 9 AM remind me to call Ahmad.
My son's birthday is on 2026-06-20. Save it and remind me before it.
What needs my attention this week?
```

And in Arabic:

```text
ذكرني بكره ٥ الصبح عندي رحلة
عندي موعد بالمستشفى ٤ العصر بعد يومين
أبي أروح النادي يوم نعم ويوم لا الساعة ٤ العصر
موعد زواجي ١-١-٢٠٢٦
```

When you reopen the CLI, MohaMind reloads recent conversation history for that chat and shows a compact recap if past messages exist.

## How The Agent Thinks About Your Data

For reliable behavior, MohaMind separates user input into different buckets.

### 1. Reminders

Use reminders when you need an alert at a specific time.

Examples:

- `ذكرني بكره ٧ الصبح عندي اجتماع`
- `Remind me in two days about the hospital appointment at 4 PM`
- `ذكرني كل يومين أروح النادي الساعة ٤ العصر`

Stored in:

- `memory/reminders.md`

Executed by:

- the reminder engine, which runs every 30 minutes when the scheduler is active

### 2. Tasks

Use tasks when something needs doing, even if it is not tied to an exact alert time.

Examples:

- `Add task renew car insurance`
- `أضف مهمة شراء الدواء بعد بكره`

Stored in:

- `memory/tasks.md`

Used by:

- the CLI task views
- the attention radar
- reminder logic for due tasks

### 3. Occasions

Use occasions for annual or meaningful dates such as birthdays and anniversaries.

Examples:

- `موعد زواجي ١-١-٢٠٢٦`
- `Add Sara's birthday on 2026-08-18`

Stored in:

- `memory/occasions.md`

Used by:

- the occasion parser
- the reminder engine
- the attention radar

### 4. Long-Term Trackers

Use the domain trackers for facts and ongoing records:

- `family.md`
- `vehicle.md`
- `finances.md`
- `health.md`
- `documents.md`
- `relationships.md`

Examples:

- hospital appointments and family appointments
- vehicle service history and next service
- OpenAI subscription renewal
- medications and doctors
- passports and expiring documents

## Arabic And Dialect Support

MohaMind does not require formal Arabic.

It is designed to handle normal, spoken Arabic and Saudi/Gulf phrasing. The current normalization layer helps the agent interpret:

- Arabic digits like `١٤` and `٧`
- `بكره` as tomorrow
- `بعد بكره` as the day after tomorrow
- `٤ العصر` as `16:00`
- `٥ الصبح` as `05:00`
- `يوم نعم ويوم لا` as every two days

This means inputs like the following are valid:

```text
ذكرني بكره ٥ الصبح
عندي موعد بالمستشفى ٤ العصر
بعد بكره لازم أشتري الدوا
أبي أروح النادي يوم نعم ويوم لا
```

One important rule still applies:

- if you say only `الساعة ٤` without `الصبح`, `العصر`, or `المساء`, that is naturally ambiguous

For maximum reliability, specify the time period when it matters.

## Core CLI Commands

| Command | What it does |
| --- | --- |
| `/help` | Show available commands |
| `/majlis` | Open the command center |
| `/today` | Show today's overview |
| `/radar` | Show ranked attention items |
| `/tasks` | List active tasks |
| `/reminders` | Show scheduled reminders |
| `/remind <text>` | Create a reminder from natural language |
| `/add task <text>` | Add a task quickly |
| `/done <text>` | Complete a task |
| `/search <query>` | Search structured memory |
| `/recall <query>` | Search memory and past conversations |
| `/memory` | Preview memory files |
| `/briefing` | Generate the daily briefing |
| `/review` | Generate the weekly review |
| `/calendar` | Show calendar snapshot |
| `/config` | Show current configuration |
| `/doctor` | Check configuration health |

## Telegram Usage

Telegram is optional, but it is the best surface for receiving reminders and proactive messages.

Set these values in `.env`:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Then run:

```bash
uv run mohamind --bot
```

Or:

```bash
uv run mohamind --all
```

Telegram supports commands and free-form chat. You do not need to talk like a command interface all the time.

## Scheduler And Proactive Behavior

When the scheduler is active, MohaMind runs recurring background jobs for:

- daily morning briefing
- reminder checks every 30 minutes
- expiry monitoring
- weekly review
- social pulse
- pregnancy update checks
- monthly subscription review

This behavior is configured in [moha_mind/scheduler/jobs.py](./moha_mind/scheduler/jobs.py).

## Memory Model

MohaMind keeps memory understandable on purpose.

### Structured Long-Term Memory

Main files under `memory/`:

- `profile.md`
- `family.md`
- `tasks.md`
- `reminders.md`
- `occasions.md`
- `vehicle.md`
- `finances.md`
- `health.md`
- `home.md`
- `documents.md`
- `travel.md`
- `learning.md`
- `shopping.md`
- `relationships.md`
- `energy_log.md`

Additional files:

- `memory/daily_log/YYYY-MM-DD.md`
- `memory/notes/*.md`

### Persistent Session Recall

Conversation history is stored separately in:

- `memory/sessions.db`

This gives the agent two memory layers:

- curated long-term memory for durable facts
- persistent session history for conversational recall

### How Recall Works

- `/search` looks through the structured Markdown files
- `/recall` looks through both structured memory and past conversations
- normal chat can also pull relevant conversation context automatically

## Integrations

### LLM Providers

- `z.ai` is the default primary provider
- `OpenAI` is supported as primary or fallback

### Google Calendar

1. Create Google Calendar OAuth credentials.
2. Put the file at `credentials/google_credentials.json`, or update `GOOGLE_CREDENTIALS_PATH`.
3. Keep `GOOGLE_TOKEN_PATH` pointed at a writable token file.

### Microsoft Outlook / Graph

Set these values in `.env`:

- `MS_CLIENT_ID`
- `MS_CLIENT_SECRET`
- `MS_TENANT_ID`
- `MS_TOKEN_PATH`

## Minimal Configuration

Most users only need these values:

| Variable | Required | Purpose |
| --- | --- | --- |
| `PRIMARY_LLM` | yes | `zai` or `openai` |
| `ZAI_API_KEY` | if using z.ai | z.ai API key |
| `OPENAI_API_KEY` | if using OpenAI | OpenAI API key |
| `TIMEZONE` | yes | your local timezone |
| `MORNING_BRIEFING_TIME` | no | daily briefing time |
| `WEEKLY_REVIEW_DAY` | no | weekly review day |
| `WEEKLY_REVIEW_TIME` | no | weekly review time |
| `MEMORY_DIR` | no | defaults to `./memory` |

Use `.env.example` as the full reference.

## Architecture

```text
MohaMind/
├── moha_mind/
│   ├── agent/            core agent, memory, session recall, prompting
│   ├── cli/              interactive terminal app
│   ├── mcp_servers/      task, reminder, family, finance, memory, attention
│   ├── scheduler/        background jobs and proactive checks
│   ├── telegram_bot/     Telegram handlers
│   └── utils/            timezone, date, Arabic support helpers
├── memory/               user memory files and sessions.db
├── credentials/          optional calendar credentials
└── tests/                test suite
```

## Troubleshooting

- Run `uv run mohamind doctor` to check `.env`, API keys, memory, and credentials directories.
- If you only want the CLI, leave Telegram blank.
- If calendars are not configured, the app still runs. Calendar commands simply show those integrations as unavailable.
- If you want to reset session history, remove `memory/sessions.db`.
- If you want to inspect the durable memory, open the Markdown files under `memory/`.

## Quality

Current local verification:

- `uv run pytest -q` -> `400 passed`
- `uv run ruff check .` -> clean

## Development

Install dependencies:

```bash
uv sync
```

Run tests:

```bash
uv run pytest
```

Lint and format:

```bash
uv run ruff check .
uv run ruff format .
```

Key directories:

- `moha_mind/agent/` - core agent loop, memory, recall, prompting
- `moha_mind/cli/` - interactive CLI
- `moha_mind/mcp_servers/` - task, reminder, family, finance, memory, and calendar tools
- `moha_mind/scheduler/` - briefings, reminders, expiry checks, review jobs
- `moha_mind/telegram_bot/` - Telegram interface
- `memory/` - persistent user data
- `tests/` - automated tests

## License

MIT. See [LICENSE](LICENSE).
