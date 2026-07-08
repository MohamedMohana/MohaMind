# AGENTS.md - Guide for AI Agents

## Project Overview
MohaMind is a personal AI agent that connects to Telegram, Google Calendar, and Microsoft Outlook. It uses z.ai (Zhipu GLM) as the primary LLM with OpenAI fallback. Memory is stored as human-readable markdown files.

## Tech Stack
- Python 3.12+ with `uv` package manager
- z.ai GLM-4 via OpenAI-compatible API (primary), OpenAI GPT-4o-mini (fallback)
- MCP (Model Context Protocol) for tool servers
- python-telegram-bot v21+ for Telegram
- APScheduler for scheduled jobs
- Pydantic Settings for configuration

## Commands

### Install dependencies
```bash
uv sync
```

### Run the agent
```bash
uv run mohamind
```

### Run tests
```bash
uv run pytest
```

### Lint
```bash
uv run ruff check .
uv run ruff format .
```

## Code Style
- Line length: 120 characters
- No comments unless asked
- Follow existing patterns in the codebase
- Async by default for all I/O operations
- Use Pydantic for data validation

## Project Structure Conventions
- `moha_mind/agent/` - Core agent logic (LLM, memory, tools)
- `moha_mind/mcp_servers/` - MCP tool servers (each in own subdirectory)
- `moha_mind/telegram_bot/` - Telegram bot interface
- `moha_mind/scheduler/` - Scheduled jobs (briefing, reminders, etc.)
- `moha_mind/utils/` - Shared utilities
- `memory/` - Persistent markdown memory files (gitignored personal data)
- `tests/` - Test suite mirroring source structure

## Key Patterns
- Memory files are markdown with `## Sections` and `- list items`
- Built-in MCP servers are in-process classes with a `handle_tool(tool_name, arguments)` async method
- External MCP servers (real protocol, stdio/HTTP) are configured in `mcp_servers.json` and connected via `mcp_servers/external.py`; their tools are exposed as `<server>_<tool>`
- Agent core registers tool handlers from MCP servers at bootstrap; external tools pass their own JSON schema to `register_tool(..., schema=...)`
- Scheduler jobs are registered in `scheduler/jobs.py`
- All timestamps are in KSA timezone (Asia/Riyadh, UTC+3)

## Environment Variables
See `.env.example` for all required configuration.
