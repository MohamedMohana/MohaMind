# Your first MohaMind session

Run commands from your MohaMind directory so the agent uses the same `.env` and
memory directory on every start. Existing users should keep their current directory
and `MEMORY_DIR`; setup does not reset memory.

## 1. Try the offline demo

After cloning the repository and installing dependencies with `uv sync`:

```bash
uv run mohamind demo
```

This uses fictional tasks in a temporary directory. No API key or personal memory
is needed. If `uv` is unavailable, follow the installation link in the README.

## 2. Configure chat

Have a provider API key ready, then run:

```bash
uv run mohamind setup --quick
uv run mohamind doctor
```

Choose a provider, enter its key, and choose a timezone and language. A new setup
uses one provider; optional integrations can be configured later. Doctor checks
local configuration without making paid requests. It cannot verify that your API
key has credit or that a model is available.

## 3. Create something useful

```bash
uv run mohamind
```

Inside the agent:

```text
/add task Try MohaMind
/tasks
/remind Tomorrow at 9 AM KSA, remind me to try MohaMind
/reminders
```

The task commands work locally. The natural-language reminder command uses your
configured model. Check the reminder text and exact date in `/reminders`; do not
rely only on the model's confirmation. Dates currently use Asia/Riyadh (UTC+3).

Arabic alternative:

```text
/remind ذكرني بكرة الساعة ٩ الصبح بتوقيت السعودية أجرب MohaMind
```

## 4. Verify persistence

Use `/quit`, start `uv run mohamind` again from the same directory, then run
`/tasks` and `/reminders`. The saved items should still be there.

## 5. Enable notifications when ready

Saving a reminder and delivering a notification are separate steps. For Telegram,
run full setup with `uv run mohamind setup`, configure the bot token and your private
chat ID, and keep `uv run mohamind --bot` or `uv run mohamind --all` running.

For WhatsApp Message Yourself, follow [QR linking](whatsapp.md), then run
`uv run mohamind whatsapp --schedule`. Run only one scheduler for the same memory directory.

Optional calendars and advanced memory features are not required for this walkthrough.

## If something fails

| Symptom | Next step |
| --- | --- |
| Setup rejects the timezone | Use an IANA name, for example `Asia/Riyadh` or `Europe/London` |
| Doctor rejects the key | Replace example text such as `your-zai-api-key` with your own key |
| Chat cannot connect | Check your provider's key, account credit, endpoint, and configured model |
| Edited `.env` seems ignored | Exported shell variables override `.env`; remove stale overrides |
| Saved items seem missing | Return to the original working directory and verify `MEMORY_DIR`; do not reset files |
| A reminder never arrives | Check the messaging configuration and keep its process running |

For bug reports, include the failing command and expected behavior. Omit API keys,
session credentials, and personal memory.
