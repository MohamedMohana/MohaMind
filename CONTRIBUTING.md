# Contributing to MohaMind

Bug fixes, documentation, translations, integrations, and ideas are welcome.
For larger changes, open an issue first to discuss the behavior you want to add.

## Local development

```bash
git clone https://github.com/MohamedMohana/MohaMind.git
cd MohaMind
uv sync
uv run mohamind demo
uv run pytest -q
uv run ruff check .
```

Python 3.12 or newer is required. The demo and tests work without provider keys.
Run `uv run mohamind setup` if you want to try AI chat with your own credentials.

## Pull requests

1. Create a branch for one focused change.
2. Follow the patterns in `AGENTS.md`: async I/O, Pydantic validation, and a
   120-character line limit.
3. Add tests for new behavior and bug fixes, using temporary memory directories
   and mocked external services. Avoid paid API calls in tests.
4. Run the test suite and Ruff, and format the files you changed.
5. Describe the user-visible change and how you verified it in your pull request.

## Personal data

Keep `.env`, credentials, `mcp_servers.json`, logs, and personal memory out of
commits. Memory examples belong in `memory/templates/` and must contain only
empty scaffolds or fictional data. Review `git diff --cached` before committing.
Use fictional examples in bug reports and remove tokens and personal details
from logs or screenshots.

## Reporting bugs

Include the command you ran, expected and actual behavior, operating system,
Python version, and a small reproduction. State whether the problem occurs in
CLI, Telegram, or both. Never include API keys or Telegram bot tokens.
