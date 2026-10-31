# Tests and acceptance

Run `./scripts/build.sh`, `./scripts/test.sh`, then `python3 scripts/smoke.py` from the root.

Automated suite covers routing/refusal; request types and size boundaries on command input; traversal and symlinks; exclusive creation/no overwrite; independent evidence; verification failure retaining the created effect; persistence/interrupted recovery; running and queued cancellation; stop/resume; concurrent submissions; HTTP authentication, Origin/Host checks, unknown routes, task read/list/cancel and control endpoints.

Real Mac smoke opens Calculator and Finder and verifies bundle IDs with NSWorkspace, creates and reads back a sample, independently lists the demo directory, rejects /etc, checks stop/resume, restarts the service to verify history, and closes the parent pipe to verify graceful shutdown. It retains evidence under artifacts/.

Native UI checks: initial connected state, create sample via suggestion, inspect result/evidence/authorization, Stop All disables commands, Resume re-enables, forced backend crash changes UI to stopped and disables commands, Restart Executive reconnects with preserved history, quit/relaunch retains history. Inspect layout with the native screenshot tool. No Accessibility permission is needed by JARVIS itself.

Service tests need local network binding. The Codex execution sandbox initially denied bind; rerunning with permitted loopback networking passed. This is an execution-environment limitation, not a reason to weaken runtime authentication.
