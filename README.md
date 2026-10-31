# JARVIS — local Mac executive

Phase 0–1 implementation: a SwiftUI menu-bar/window app with a supervised Python service, authenticated loopback API, SQLite history, a single task queue, scoped policy checks, and verified demo actions. No model, cloud account, package installation, or recurring subscription is required.

## Build and run

From this repository:

```sh
./scripts/build.sh
./scripts/run.sh
```

The app is `.build/JARVIS.app`. It is ad-hoc signed for local development, not notarized for distribution. Build requires the installed Xcode Command Line Tools, Python 3.14, and macOS 14 or newer; tested only on macOS 27.0.1 / Apple M5. The package records the Python and repository paths at build time: rebuild after moving the repository or changing Python.

## Commands

- `open calculator`
- `open finder`
- `list demo folder` (also `list files`)
- `create sample file` (also `create a sample text file`)

Case and whitespace are normalized. Unknown requests are recorded as failed with supported suggestions and execute nothing. Select a task to see results, authorization, verification evidence, and progress. Stop All pauses dispatch and cancels outstanding tasks; Resume re-enables it. Cancel does not undo completed actions. App launches are checked using NSWorkspace; created files are read back and hashed.

Runtime data stays in ignored `data/`: SQLite history and `workspace/` sample files. The app does not read your other folders. Closing its window keeps the menu-bar app alive. Quit stops the backend; a crash is shown in the UI with a Restart Executive button. Interrupted tasks are retained but never replayed automatically.

## Verify

```sh
./scripts/test.sh
python3 scripts/smoke.py
```

Tests require loopback networking. The smoke test intentionally opens Calculator and Finder and creates isolated files in `artifacts/smoke-data/workspace/`; results go to `artifacts/smoke-results.json`. Build first. No test sends data externally.

See `docs/STATUS.md` for observed results, `docs/API.md` for the contract, and `docs/RISKS.md` for practical limits. Both original specifications remain unchanged. Voice, local models, second brain, browser control, OpenCode, and Agent Factory are not implemented in this release.
