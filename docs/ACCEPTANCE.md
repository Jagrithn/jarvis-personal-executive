# Owner acceptance sequence — 1 November 2026

The owner requests one completed feature at a time: implement, run automated and real checks, rebuild, then wait for their full test before proceeding. Do not start the next feature until the owner accepts the current one or requests changes.

## Current: everyday conversation

- Plain greetings, explanatory questions and simple follow-ups route to local chat without the chat: prefix.
- Last three successful chat exchanges provide bounded context. Existing task history stores these exchanges; restarting retains them.
- Conversation has no execution tools. Exact actions still use adapters; model-proposed actions still require confirmation.
- Local model final-answer formatting strips thinking markup. Empty/incomplete answers fail visibly.
- The chat: prefix remains an explicit fallback for phrasing outside the deterministic conversation patterns.

Owner test:
1. Hi
2. What can you do?
3. Explain gravity and give one simple example.
4. Tell me this code word back: saffron42.
5. What code word did I just tell you?
6. Open calculator
7. Ask another question and press Cancel task while it is running; then ask Hi again.

Pending owner acceptance. This milestone does not add general autonomous task planning or new account integrations.

## Subsequent sequence (not yet authorized to advance past current acceptance)

1. Reliable natural-language access to currently implemented capabilities and clear unsupported-request responses.
2. Full voice error/stop/playback acceptance, then browser acceptance.
3. Second-brain ingestion and memory controls acceptance.
4. Reliable scoped OpenCode build with independent tests.
5. Registered workers and schedule controls acceptance.
6. Agent Factory, recovery/backup, packaging and explicitly selected external integrations as separate milestones.

Hermes/OpenClaw remain project-local installations. Global terminal shortcuts and any integration must be presented and tested as separate deliverables.
