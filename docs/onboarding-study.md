# Five-person onboarding study

Status: prepared, not conducted. Automated checks and code inspection are not a
substitute for observations from new users.

## Participants and preparation

Recruit five people who have never used MohaMind. Include Arabic and English users
and record each participant's operating system and terminal experience. Participants
provide their own API key privately. Do not collect keys, personal memory, or chat logs.

Use a clean test directory and fictional tasks. Record the Git revision, Python and
uv versions, OS, and whether Python, uv, and an API key were ready beforehand.
Report dependency installation time separately so slow downloads remain visible.

## Session script

Tell each participant: “Use the README to set up MohaMind, create a task, save a
reminder for tomorrow at 9 AM KSA, then restart and find both again. Explain what
you think will happen when the reminder becomes due.”

Start the timer when they open the README. Let them work without coaching. If they
are blocked, record the last action and exact confusion before offering help.
Mark any assisted task separately. Stop at ten minutes to record the result, then
allow completion and ask what was most confusing.

Ask them to find the offline demo before entering a key. Do not tell them which
commands to type unless measuring an explicitly assisted recovery.

## Record results

Use participant IDs only. Leave unobserved values blank; never fill them with estimates.

| ID | OS / experience | Language | Install minutes | Setup minutes | Task saved | Reminder correct | Survives restart | Understands delivery | Help needed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | | | | | | | | | |
| P2 | | | | | | | | | |
| P3 | | | | | | | | | |
| P4 | | | | | | | | | |
| P5 | | | | | | | | | |

For each obstacle, record the step, what the participant expected, what happened,
whether it blocked completion, and a proposed fix. Use redacted error messages.

## Acceptance and follow-up

Target: five participants independently finish the setup, task, reminder, and
restart checks within ten minutes with prerequisites ready. Report total installation
time too. A stored reminder is successful only if its exact timestamp is correct.
Notification delivery is a separate test after a messaging channel is connected.

Fix blockers first, then repeated confusion. Create one issue per concrete obstacle
with a reproduction and acceptance criteria. Repeat affected tasks with new participants.

## Findings from code inspection in this development pass

These are engineering findings, not participant feedback:

- Quick setup previously continued through optional integration and memory prompts.
- The separate first-run flow overwrote existing `.env` settings.
- Settings loaded before first-run setup could retain the old key in the same process.
- Placeholder keys and inconsistent `.env` parsing could make setup and doctor disagree.
- A successful doctor exit did not distinguish missing configuration from healthy configuration.

Regression tests now cover these paths using temporary directories and fictional data.
