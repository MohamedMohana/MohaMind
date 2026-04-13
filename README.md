# MohaMind

MohaMind is a CLI-first personal AI agent for tasks, reminders, family events, bills, documents, and follow-ups.

The intended path is simple:

- run it from the terminal
- configure it with one wizard
- keep memory in plain Markdown under `memory/`
- add Telegram or calendar integrations later if you want them

MohaMind uses z.ai (GLM) by default and can fall back to OpenAI.

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-111827.svg)](LICENSE)

## Quick Start

### Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- one API key:
  - [z.ai](https://open.bigmodel.cn)
  - [OpenAI](https://platform.openai.com/)

You do not need Telegram, Google Calendar, or Outlook to start.

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

The setup wizard writes `.env` and asks only for:

- your primary provider
- one API key
- your timezone
- optional Telegram settings

If you skip setup and run `uv run mohamind` with no API key configured, MohaMind starts a first-run onboarding flow and writes `.env` for you.

### Run

```bash
uv run mohamind
```

Other useful entry points:

```bash
uv run mohamind "Plan my week"
uv run mohamind -p "What needs my attention today?"
uv run mohamind doctor
uv run mohamind --bot
uv run mohamind --all
```

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
/search passport
/memory
```

Natural language works too:

```text
Tomorrow at 9 AM remind me to call Ahmad.
My son's birthday is on 2026-06-20. Save it and remind me before it.
What needs my attention this week?
```

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
| `/search <query>` | Search memory |
| `/memory` | Preview memory files |
| `/briefing` | Generate the daily briefing |
| `/review` | Generate the weekly review |
| `/calendar` | Show calendar snapshot |
| `/config` | Show current configuration |
| `/doctor` | Check configuration health |

## Optional Telegram And Calendar Setup

Get the CLI working first. Then add integrations.

### Telegram

Set these values in `.env`:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Then run one of:

```bash
uv run mohamind --bot
uv run mohamind --all
```

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

## Memory

MohaMind stores long-term memory in readable Markdown under `memory/`.

Main files:

- `profile.md`
- `family.md`
- `tasks.md`
- `reminders.md`
- `occasions.md`
- `documents.md`
- `finances.md`
- `health.md`
- `relationships.md`
- `shopping.md`
- `vehicle.md`

Additional memory surfaces:

- `memory/daily_log/YYYY-MM-DD.md` for daily activity summaries
- `memory/notes/*.md` for free-form notes

The rule is simple:

- durable facts belong in the structured category files
- daily context belongs in `daily_log/`
- loose capture belongs in `notes/`
- recall happens by reading and searching those files, not by hiding state in a private database

That is the useful memory lesson from Hermes-style agents: keep long-term memory curated instead of burying everything in chat history. MohaMind follows the curated Markdown part today. It does not yet have Hermes-style indexed session search and recap, so the current system stays simple, editable, and transparent.

## Minimal Configuration

Most people only need these values:

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

## Troubleshooting

- Run `uv run mohamind doctor` to check `.env`, API keys, memory, and credentials directories.
- If you only want the CLI, leave Telegram blank.
- If calendars are not configured, the app still runs. Calendar commands will simply show the integrations as unavailable.

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

- `moha_mind/agent/` - core agent loop and memory
- `moha_mind/cli/` - interactive CLI
- `moha_mind/mcp_servers/` - task, memory, reminder, family, social, and calendar servers
- `moha_mind/scheduler/` - briefings, reviews, reminder checks
- `moha_mind/telegram_bot/` - Telegram interface
- `memory/` - persistent user data
- `tests/` - test suite

## License

MIT. See [LICENSE](LICENSE).
