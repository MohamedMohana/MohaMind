# memory/ — private, local-only data

Everything inside this directory is **gitignored on purpose**. This is where
MohaMind stores your personal life context — health, finances, family,
appointments, conversation history, audit log, semantic index, etc.

## What gets created here

| Path | Purpose |
| --- | --- |
| `profile.md` | Your personal profile |
| `family.md`, `relationships.md` | People in your life |
| `tasks.md`, `reminders.md`, `occasions.md` | What needs doing / when |
| `finances.md`, `health.md`, `documents.md` | **Sensitive** — tier-1 categories |
| `vehicle.md`, `home.md`, `travel.md`, `shopping.md`, `learning.md`, `energy_log.md` | Long-term trackers |
| `daily_log/YYYY-MM-DD.md` | Day-by-day activity log |
| `notes/*.md` | Free-form notes |
| `sessions.db` | Conversation recall (SQLite) |
| `.semantic_index.db` | Vector index for hybrid search |
| `.history.jsonl` | Provenance log (enables `/undo` and `/why`) |
| `.summaries/` | Rolling per-category summaries |
| `.pending_consolidations.jsonl` | Nightly consolidator queue |

## Why is it gitignored?

Because this is **your life data**. It must never be pushed to GitHub — not
even accidentally. The `.gitignore` rule at the repo root ignores everything
under `memory/` except this README, the `.gitkeep` placeholder, and the
empty scaffolding in `memory/templates/`.

On first run, MohaMind copies files from `memory/templates/*.md` into
`memory/*.md` so you start with the expected section structure but no
personal content. Edit the real files however you like — they stay local.

## Backing it up

Back up the directory directly with any tool you trust (rsync, Time Machine,
encrypted cloud sync, etc.). Do **not** put it in a git repo you push
anywhere public.

## Starting fresh

Delete any file or the whole directory — MohaMind will recreate the files it
needs on the next run. Your provenance log (`/undo`, `/why`) and semantic
index are derived from the markdown files, so they can be rebuilt too
(`/reindex`, `/refresh_summaries`).
