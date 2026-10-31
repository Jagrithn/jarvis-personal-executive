# Phase 0–1 status — 31 October 2026

Implemented and locally demonstrated on the owner's Apple M5 MacBook Air (16 GB, macOS 27.0.1).

## Delivered

Native SwiftUI window + menu bar; deterministic typed commands and suggestions; history/transcript, progress, authorization and evidence; authenticated private loopback service; supervised child startup and crash recovery; SQLite persistence; one queue; scoped policy; cancellation; Stop All/Resume; four real adapters with independent verification. Build/run/test scripts and a locally signed `.build/JARVIS.app` are available. Both original specification files are preserved unchanged.

## Observed evidence

- Swift app and NSWorkspace verifier compiled successfully; local ad-hoc signing succeeded.
- `./scripts/test.sh`: **12 tests passed**, final run 1.204 seconds. Detailed log: `artifacts/tests.log`.
- `python3 scripts/smoke.py`: **passed** all four real commands, independent evidence, rejected external path, stop/resume, history after restart, and graceful shutdown via parent-pipe EOF. Machine-readable receipts: `artifacts/smoke-results.json`.
- Native window inspected with computer-use accessibility and screenshot tools: live connected status, sample creation, result/read-back hash, scope and progress; Stop All disabled commands and Resume restored them.
- Forced backend crash: UI displayed “Executive stopped” and disabled actions. Restart Executive reconnected and preserved history.
- Quit/relaunch and final rebuild: history retained, local service reconnected. Typed `list demo folder` submitted successfully and displayed independent listing evidence.
- Final app left running for the owner. Calculator and Finder were opened during smoke testing; no personal documents were edited.

## Dependencies and permissions

No third-party executable dependencies installed. Existing Swift/AppKit/SwiftUI, Python standard library and SQLite used. No microphone, Accessibility, Full Disk Access, screen-recording, account, or cloud permissions requested by JARVIS. Test execution required escaping Codex's loopback-bind restriction; local Git initialization required access to protected `.git` metadata. No unresolved approval blocks.

## Known limits and next step

See RISKS.md. This is a local development package, with build-time absolute paths and ad-hoc signing. It provides four deterministic commands, not general AI reasoning. Phase 2 local reasoning/model evaluation is the next milestone and has not begun. Voice, personal knowledge, OpenCode and Agent Factory remain deferred. No wrong-port UI injection test was performed; network/auth failures are covered at the API layer and an actual backend crash was checked in the native UI.
