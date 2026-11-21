# JARVIS next phases implementation plan

**Goal:** Extend the working app with local voice, browser reading, reviewable memory, and bounded reusable workflows, then verify the combined app.
**Architecture:** Keep SwiftUI and the authenticated single-queue Python executive. Each capability has routing, policy, adapter and independent evidence. OpenJarvis supplies isolated memory/inference primitives; Hermes/OpenClaw remain optional installed tools.
**Spec:** PLAN (1).md, newer user authorization to build subsequent phases.
**Execution:** Native integration with separate voice, browser and workflow module workers. Preserve existing uncommitted work in this checkout; do not copy ignored native runtimes into a new worktree.

## Constraints and review focus
- No outbound messages, account connections, publishing or payments.
- Model prose cannot authorize tools or serve as verification.
- Source deletion/change must prevent stale memory answers.
- Network browser permission must appear in scope and require confirmation.
- Mic capture must be explicitly requested; offline recognition must fail truthfully when unavailable.
- Cancellation, restart and stop-all retain completed effects and prevent unintended replay.
- A registered worker cannot expand its fixed template capabilities.

## Tasks
- [ ] Baseline: run standard and real OpenJarvis tests; retain logs.
- [ ] Memory: add failing stale-source/review/export/forget tests, implement and verify with real native index. Forget clears index only; task history/export copies explicitly remain.
- [ ] Voice: native push-to-talk, offline recognition, review-before-submit and local speech; compile and document device-only checks.
- [ ] Browser: bounded public read-only Playwright context, network validation, confirmation, dependency setup and tests.
- [ ] Workflows: source-grounded reports, communication drafts, organization plans, versioned fixed-template registration and artifact verification.
- [ ] Integrate all routes/scopes/approval handling with API tests; build the app and run real smoke tests.
- [ ] Assess remaining Phase 5 coding-worker and Phase 6 scheduling requirements against actual isolation/runtime evidence; implement where enforceable and explicitly record incomplete milestones.
- [ ] Update API, status and setup documentation with exact verified coverage and limitations.

## Progress
- Baseline: 36 tests, 31 passed and 5 optional native tests skipped; separate real OpenJarvis run 5/5 passed. Initial restricted-sandbox loopback errors resolved by executing integration tests with loopback permission.

## Owner-controlled acceptance, 1 November 2026

The owner now requires one completed feature followed by their testing before advancing. See docs/ACCEPTANCE.md. Current feature is plain-language conversation and bounded follow-up context. Broad-phase implementation is paused at this acceptance boundary, not declared complete. Prior baseline/voice/browser/memory/workflow code remains preserved.
