# WhatsApp with QR linking

Talk to your existing MohaMind agent from WhatsApp's **Message Yourself** chat.
The agent uses your configured `MEMORY_DIR`; linking does not replace or reset memory.
WhatsApp conversations have their own history while sharing your saved facts and tasks.

This uses [Baileys](https://github.com/WhiskeySockets/Baileys), the same type of
WhatsApp Web bridge described in [Hermes's WhatsApp guide](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/whatsapp).
It is unofficial, so account restrictions and compatibility changes are possible.
The pinned Baileys release is currently a release candidate. Live account compatibility
must be verified by pairing; offline tests do not establish it.

## Link your account

Requirements: Node.js 20 or newer with npm, WhatsApp on your phone, and an existing
MohaMind checkout. Run all commands from the directory containing your existing `.env`.

```bash
uv run mohamind whatsapp setup
```

Setup installs the optional Node dependencies locally and displays a QR code.
On your phone, open **WhatsApp → Settings → Linked Devices → Link a Device**, then
scan the code. Setup saves the session and exits. Pairing does not start the agent,
read your memory, or send messages.

If there is already a saved session, setup checks that it connects. Stop any running
MohaMind WhatsApp process before pairing again. Never delete your memory to fix pairing.

## Start chatting

```bash
uv run mohamind whatsapp
```

Open Message Yourself on the linked account and send `/help`, or ask:

```text
What tasks do I have?
Remember that my fictional project is called Cedar.
What do you remember about Cedar?
```

Replies start with `[MohaMind]`. Keep the terminal process running; Ctrl+C stops it.
This initial version supports text self-chat only. Other contacts, groups, status
updates, imported history, edits, voice notes, and attachments are not forwarded to
the agent. It does not add a tool for messaging arbitrary contacts.

Only messages sent while the bridge is running are accepted. Send a fresh message
after startup; old self-chat messages are not imported. Requests are processed in order.
Messages over 8,000 characters are rejected, and replies are split into smaller chunks.
The queue holds up to 32 pending requests; overflow is rejected and logged locally.

## Scheduled notifications

To deliver your existing scheduler's reminders and briefings to Message Yourself:

```bash
uv run mohamind whatsapp --schedule
```

Use a single scheduler process for a memory directory. Stop the Telegram scheduler
(`--bot` or `--all`) before enabling WhatsApp scheduling to avoid duplicate jobs.
Without `--schedule`, WhatsApp provides chat only. Reminder timing follows the existing
MohaMind scheduler; reminder dates currently use Asia/Riyadh.

## Session storage and recovery

| Setting | Default | Purpose |
| --- | --- | --- |
| `WHATSAPP_SESSION_DIR` | `./credentials/whatsapp` | Linked-device credentials, bridge dependencies, and message receipts |
| `WHATSAPP_NODE_PATH` | `node` | Node executable name or path |

The default credentials directory is gitignored. Keep custom session directories
private too: linked-device credentials grant account access. QR codes appear only
in the pairing terminal; they are not written to application logs.

The bridge communicates with Python over local subprocess pipes, without a public
webhook or listening HTTP port. Only accepted self-chat text reaches the configured
agent and its model provider. The normal MohaMind memory and privacy settings apply.

Message receipts store hashed account/message identifiers separately from memory.
A request is recorded before invoking the agent, so reconnects or restarts do not
automatically replay an action. If the process fails during a request, check the
resulting state before sending a new request; a reply failure does not undo an action.

| Problem | Recovery |
| --- | --- |
| Node.js missing or too old | Install Node.js 20+ and npm, or set `WHATSAPP_NODE_PATH` |
| Dependencies missing after an update | Run `uv run mohamind whatsapp setup` again |
| QR expired | Wait for the refreshed code or restart setup |
| Session logged out | Stop the bridge, inspect Linked Devices, then run setup again |
| No answer | Use Message Yourself on the linked account and send a new text message |
| Lost connection | Temporary failures retry with backoff; persistent failures exit with guidance |

Unlink MohaMind from **WhatsApp → Linked Devices** to revoke access. Your MohaMind
memory remains in `MEMORY_DIR` and is independent of the WhatsApp session.
