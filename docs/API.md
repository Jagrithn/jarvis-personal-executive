# Local API v1

Base: `http://127.0.0.1:<assigned-port>/v1`. All GET and POST endpoints require `Authorization: Bearer <launch-token>`. Browser Origin headers are rejected, as are Host headers other than the exact bound loopback host/port. Tokens are never written to files, command-line arguments, or request logs. No CORS support. POST bodies are JSON, at most 4096 bytes.

| Method | Path | Result |
|---|---|---|
| GET | /health | status, api_version, paused |
| GET | /capabilities | array of id, title, commands |
| GET | /tasks | newest-first task array |
| GET | /tasks/{id} | one task |
| POST | /tasks | submit {command: string, path?: string}; return recorded task |
| POST | /tasks/{id}/cancel | request cancellation; return task |
| POST | /stop-all | pause dispatch, cancel outstanding work |
| POST | /resume | re-enable dispatch |
| POST | /shutdown | stop work and shut down service |

Control endpoint bodies are `{}`. Submissions reject unknown properties and require 1–500 characters after whitespace trimming (maximum length checked on input). Optional path is only for validating the designated workspace; it cannot select an arbitrary target. A policy/command rejection returns HTTP 200 with a failed task so it remains visible in history. Malformed requests and submissions while paused return 400; missing tasks/routes 404; missing/incorrect authentication 401; origin/host rejection 403; oversized bodies 413.

Task fields: id (UUID), command, capability (nullable capability ID), scope (paths and network), approval (kind/source/paths/network/capability or empty on rejection), state, created_at/updated_at (UTC ISO timestamps), events (time/state/message), result (nullable capability-specific object), error (nullable string), evidence (array of verifier objects). Swift TaskRecord/TaskEvent and JSONValue decode the shared wire contract; Python validates submission types at the boundary.

Capability results: apps return bundle_id and effect; files.list returns entries (names only); files.sample returns filename, content, and effect. Evidence includes observed running bundle identifier or independently observed listing, or created path, byte count and SHA-256. All task state writes are committed to SQLite. Tokens are ephemeral and change on relaunch. Phase 1 has no external actions or retry endpoint.

## Phase 2 additions

See PHASE2.md for model status, proposal confirmation, awaiting_approval state, and additive task fields. Unknown requests are now interpreted locally when enabled; they do not execute without owner confirmation.

## Extended capabilities

All new actions use the same task submission/detail/approval/cancellation contract. `POST /tasks/{id}/approve` confirms a pending task exactly once. `GET /model` reports local model availability. The capability inventory is dynamic; clients must not assume four or eight entries. `health.scheduler_error` is nullable and exposes durable scheduling failures.

Pending confirmation is mandatory for memory indexing/forget, public page reads, worker registration, coding builds, schedule creation and schedule resume. Browser scope has `network: true`; all other capabilities have no external-network grant (local inference uses loopback). Authorization details are visible in the confirmation panel. Memory and registry SQLite state are maintained in the configured data directory in addition to artifact paths under workspace.

Commands/results are documented in README.md. States include `awaiting_approval`, `queued`, `running`, `succeeded`, `failed`, `cancelled`, `interrupted`. New memory search results include `stale_sources`; rejected memory excerpts/answers are withheld from normal output. Browser evidence verifies captured-text integrity only. Coding evidence is limited to passive HTML structure and sandbox probes; it is not a functional application test.

Stop All pauses schedules even if no task is running. A schedule-persistence error is reported but never prevents task cancellation. Ordinary Resume does not resume schedules. Scheduler occurrences are reserved before submission, are never automatically retried, and do not overlap for the same schedule. On restart all active schedules become paused; missed occurrences are skipped after explicit resume.
