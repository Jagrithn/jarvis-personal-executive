# JARVIS agentic milestones implementation plan

> **For agentic workers:** Implement these tasks in order. Mark a task complete only after its acceptance checks pass on the target Mac.

**Goal:** Turn JARVIS's separate tools into a goal-driven executive that can commission useful workers, evaluate new reusable capabilities, and recover safely.

**Architecture:** Retain the working Swift app and authenticated Python executive while replacing fixed command-only worker paths with versioned contracts. Keep authorization in the executive, run new capabilities in bounded workspaces, and verify effects independently. Reuse OpenJarvis for local inference and OpenCode for software work where its runtime passes real tests.

**Tech Stack:** SwiftUI/AppKit, Python 3.14, SQLite, OpenJarvis/Ollama, OpenCode, macOS sandbox, project-local browser and voice runtimes.

**Spec:** `PLAN (1).md` and `JARVIS_MASTER_CONTEXT.md`.

## Global constraints

- No worker grants itself permissions. The executive owns scoped authorization and approvals.
- External messages, posts, installs, payments and important deletes require owner confirmation.
- Model prose is never completion evidence. Verify artifacts and destination state independently.
- Preserve existing runtime data and uncommitted work. Never replay uncertain effects after restart.
- A local-first baseline remains usable without a paid model service.

## Task 1: Real software worker acceptance

**Files:** `services/executive/coding.py`, `services/executive/server.py`, `tests/test_coding.py`, `docs/CODING.md`.

- [x] Run the current OpenCode job on the actual Mac and record its result, including sandbox and model failures. Qwen3 4B timed out; Qwen2.5 7B produced a verified static artifact, including through the executive approval path.
- [ ] Specify a small runnable assignment tracker with explicit input, output and acceptance criteria. Remove the fixed passive HTML-only deliverable once the replacement is proven.
- [ ] Keep the worker confined to a fresh project and log all allowed tool use, deadline, cancellation and resource limits.
- [ ] Test a generated app in a separate verifier process with positive, negative and tampering cases; record real build/run evidence.
- [ ] Give the owner a runnable artifact and test it through JARVIS's app task lifecycle.

## Task 2: Versioned worker contracts and executive delegation

**Files:** new `services/executive/contracts.py`, `services/executive/agent.py`, `services/executive/server.py`, `services/executive/policy.py`, `tests/test_agent_bridge.py`.

- [ ] Define a validated contract with name, version, inputs, outputs, success checks, tool allowlist, path/network scope, deadline, budgets and approval class.
- [ ] Add capability discovery before planning, and prevent model-proposed steps outside the registered contract.
- [ ] Persist a multi-step plan with step states and receipts; resume only steps whose side effects are known safe to retry.
- [ ] Prove a three-step owner goal using more than one department and real read-back evidence.

## Task 3: Agent Factory v1

**Files:** new `services/executive/factory.py`, `services/executive/workflows.py`, `services/executive/scheduler.py`, `tests/test_factory.py`.

- [ ] Accept a capability request and search existing workers first.
- [ ] Produce a reviewable proposed contract and choose a deterministic workflow or reasoning worker based on the task.
- [ ] Generate candidate configuration and tests in a disposable workspace, evaluate functional, failure and permission behavior, and enforce time/tool budgets.
- [ ] Require owner approval before activation, persist immutable versions and evaluation evidence, and support disable and rollback.
- [ ] Create a research reporter and file organizer from requests; run each twice and prove scope and failure behavior.

## Task 4: Managed operation and expansion

**Files:** `services/executive/scheduler.py`, `services/executive/store.py`, `apps/mac/CommandCenter.swift`, dedicated acceptance tests and setup documentation.

- [ ] Add checkpoints, hard retry limits, duplicate-effect protection, a worker/evaluation status screen and backup/restore tests.
- [ ] Complete voice and browser failure/latency acceptance, selected-note continuity and consented service adapters.
- [ ] Test offline startup, service crash, restart, signed distribution feasibility and cross-platform architecture.
- [ ] Use real mission evaluations for computer, research, communication and software work before describing the broad vision as complete.

## Current checkpoint

The research-to-report workflow and two fixed worker templates exist. They are not automatically generated agents. The 118-test suite passed with nine optional skips on 17 November; the fixed static OpenCode preview was verified through the executive but does not satisfy the runnable software-worker or factory exit tests. Runtime acceptance and broader Phase 7 remain open.
