# MohaMind roadmap

Build a personal agent people can install, understand, and trust with everyday work.
The initial audience is individuals running their own instance. Arabic and English,
readable memory, reliable reminders, and optional integrations are the foundation.

This is a proposed order of work, not a promise that the features below already exist.
Each milestone should ship independently with examples and regression tests.

## 1. Predictable execution

Implemented in this change:

- Reject malformed JSON and non-object tool arguments before invoking handlers.
- Limit tool-call attempts across a chat turn, including large batches.
- Apply the same call limit to briefings and weekly reviews.
- Apply cooperative async tool timeouts without automatically retrying actions.
- Bound tool response sizes and mark truncation explicitly.
- Test cancellation, exhausted budgets, malformed arguments, and scheduled workflows
  without paid API calls.

Next:

- Validate arguments against each registered tool's schema, including external MCP schemas.
- Serialize overlapping turns in the same conversation while allowing independent
  conversations to progress. Test CLI and Telegram overlap.
- Add configurable whole-turn deadlines and model token budgets, including verifier calls.
- Move blocking integration calls off the event loop and test cancellation boundaries.
- Add per-tool allow/deny policies and previews for actions such as sending email or
  deleting events. Enforce policies in the dispatcher across every entry point.

Acceptance: a stalled integration does not freeze unrelated conversations; rejected
actions never reach handlers; each requested tool receives an accurate success,
failure, skipped, or unknown-outcome result.

## 2. Prove everyday task success

The existing unit suite is useful, but it does not establish real-model task success.
Create a versioned evaluation set of at least 100 fictional Arabic and English scenarios:

- Create, change, cancel, and recall reminders with exact expected timestamps.
- Ask for clarification when dates or recipients are ambiguous.
- Retrieve remembered facts and acknowledge facts that were never stored.
- Complete tasks without duplicating actions after a provider failure.
- Treat instructions inside retrieved documents and tool results as untrusted content.
- Recover from unavailable calendars, malformed tool calls, and restarts.

Keep deterministic replay tests in CI. Make live-provider evaluations opt-in and
publish the model, configuration, date, task success rate, latency, and token usage.
Score actual resulting state rather than relying only on an LLM's assessment of prose.
Report Arabic and English results separately.

Acceptance: a release includes a reproducible report and no regressions in deterministic
action correctness. Set live-model quality thresholds after recording the first baseline.

## 3. Make the first ten minutes work

- Keep the existing offline demo as the first experience.
- Test setup and doctor with people who did not build the project; improve the first
  failure they encounter rather than adding more setup questions.
- Add actionable doctor checks for provider connectivity, model tool support,
  timezone configuration, and optional integrations. Keep network checks opt-in.
- Audit hardcoded Asia/Riyadh prompts and date parsing before claiming global timezone
  support. Preserve Riyadh as the default and test daylight-saving transitions elsewhere.
- Expand CI smoke coverage to Windows and macOS before advertising verified support.

Acceptance: five new users can install, configure, create a reminder, restart, and
recall it within ten minutes using only published documentation. The offline demo
continues to require no credentials or personal data.

## 4. Make model choice practical

Custom compatible endpoints are already configurable. Build on that capability:

- Add a first-class local-provider setup path with explicit endpoint and model selection.
- Probe tool-calling support and explain unsupported capabilities before chat starts.
- Make fallback data routing visible and keep it opt-in for local-only configurations.
- Run the same evaluation scenarios against each documented provider configuration.

Acceptance: a documented local configuration completes the core task and reminder
scenarios with no outbound cloud requests; switching providers preserves memory.
Publish measured limitations and hardware requirements from tested configurations.

## 5. Give users control over memory

- Provide inspect, correct, export, and delete workflows that cover Markdown,
  conversation history, summaries, indexes, and backup retention.
- Show the source and time of recalled facts when that helps resolve conflicts.
- Test backup restoration in a fresh temporary instance.
- Keep single-instance shared memory explicit. Separate users require separate instances
  until storage, retrieval, scheduling, and authorization support tested tenant isolation.

Acceptance: users can trace and correct a remembered fact, restore an export, and
understand where deleted data can remain under their backup policy.

## 6. Grow a contributor ecosystem

- Publish a small example integration with schemas, failure behavior, and contract tests.
- Add issue templates for reproducible bugs and scoped integration proposals.
- Document compatibility expectations, release notes, and migration procedures.
- Offer opt-in local execution traces with durations, status, and token usage;
  omit tool arguments, results, credentials, and personal memory by default.
- Turn the milestones above into small issues with acceptance criteria and owners.

Acceptance: an outside contributor can implement and test an integration from the
example without changing the conversation engine or requiring production credentials.

## Release scorecard

Track these measures over time; do not claim leadership without comparative evidence.

| Measure | Evidence |
| --- | --- |
| Setup success | Observed first-run completion and time |
| Task correctness | Versioned Arabic and English evaluation reports |
| Reliability | Restart, timeout, concurrency, and duplicate-action tests |
| Efficiency | Median and p95 latency, model tokens per completed task |
| User control | Export, restore, correction, and deletion tests |
| Extensibility | Independently contributed integrations passing contract tests |
