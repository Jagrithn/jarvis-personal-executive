# Architecture

SwiftUI Window + MenuBarExtra → authenticated loopback JSON API → Python executive → policy → one worker → allowlisted adapter → independent verifier → SQLite + UI polling.

The native app supervises one child process. It creates a random launch token and writes it over a private stdin pipe, keeping that pipe open. The service binds an OS-assigned port on 127.0.0.1 and returns only the port over stdout. Parent pipe EOF or SIGTERM triggers graceful cancellation/shutdown. Polling is every 700 ms, with four-second HTTP timeouts. Backend exit disables command controls; restart is explicit.

Policy is code outside any prompt. Four fixed capabilities are preauthorized by the Phase 1 project scope. No arbitrary executable, command line, app identifier, or external file operation is accepted. Filesystem policy rejects traversal, escaped paths, and symlinks. Adapter operations use directory descriptors and O_NOFOLLOW; new files additionally use O_EXCL. Tasks store separate authorization, adapter results, and verifier evidence.

Logical boundaries live in services/executive: policy.py, adapters.py, verification.py, store.py, server.py. The Swift NSWorkspace helper verifies application identifiers without AppleScript or Accessibility permissions. The Python backend uses only its standard library. SQLite schema user_version=1 stores versioned task documents with WAL enabled; future migrations must preserve existing rows.

State transitions: queued → running → succeeded/failed/cancelled; queued → cancelled; restored queued/running → interrupted. Policy rejection goes directly to failed. Cancellation is cooperative; a completed and verified effect can finish succeeded even if cancellation arrived too late. Partial results are saved before verification. Stop All and submission are serialized under the executive lock.
