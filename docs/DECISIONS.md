# Decisions

- KEEP: newer implementation plan's Phase 0–1 sequence, confirmed by owner. Master context's voice/OpenCode first demonstrator is deferred. No data migration impact.
- KEEP: one executive, SQLite state, local-first operation, separate policy and verification. Tests exercise positive and negative outcomes.
- MODIFY: use SwiftUI/AppKit and direct Swift compiler packaging instead of Tauri/Xcode-project scaffolding. The installed toolchain successfully builds both app and verifier. No new executable dependencies.
- MODIFY: use Python standard-library HTTP rather than FastAPI. Four small local capabilities do not warrant package installation. Authenticated v1 contract leaves room for a later implementation change.
- KEEP: local runtime costs require no paid API. LLM/speech decisions remain deferred.
- MODIFY: Phase 1 approvals UI displays existing scoped grants and failures; it cannot approve new privileges. No capability in this phase requires external-action approval.
- KEEP: ad-hoc local signing only. App configuration contains absolute source/data and existing Python paths; distribution and relocation are deferred.

Discovery: MacBook Air Mac17,3; Apple M5; 16 GB memory; macOS 27.0.1; Swift 6.4; Python 3.14.6; SQLite 3.50.4; Git 2.54.0; approximately 139 GiB free at inspection. The initial sysctl query was restricted; system_profiler confirmed chip and RAM. No microphone permission was requested because voice is deferred.
