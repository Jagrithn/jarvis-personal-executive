# JARVIS — local Mac executive

A native SwiftUI command center and menu-bar app with authenticated loopback Python service, persistent tasks, scoped permissions, cancellation, approvals and evidence. It uses isolated OpenJarvis memory/inference primitives, Ollama/Qwen3 4B for local conversation, and fixed adapters for actions. It is a development build, not a completed universal autonomous assistant.

## Run

```sh
./scripts/build.sh
./scripts/run.sh
```

App: `.build/JARVIS.app`. Requires macOS, Swift/Xcode command-line tools and system Python; this machine has the additional runtimes installed. Rebuild after moving the project: the app stores the repository/Python paths. Ad-hoc signed; not notarized. Backend modules are mostly portable, but the native UI, app launch, voice and coding sandbox currently require macOS.

## Commands

| Capability | Command |
|---|---|
| Original verified actions | `open calculator`, `open finder`, `list files`, `create sample file` |
| Local conversation | Ask `What can you do?` directly; `chat:` remains available for other wording |
| Index top-level workspace .txt/.md notes | `index workspace` — confirm first |
| Search / grounded answer | `search memory: Aurora`, `ask memory: What is the deadline?` |
| Review / export / forget | `review memory`, `export memory`, `forget memory` |
| Public static web page | `read page: https://example.com` — confirm first |
| Source digest / draft / organization proposal | `create research report`, `draft workspace summary`, `plan file organization` |
| Register fixed worker | `register worker: research-reporter` or `register worker: file-organizer` — confirm first |
| Worker inventory / execution | `list workers`, `run worker: research-reporter` |
| Recurring worker | `schedule worker: research-reporter every 3600` — seconds, confirm first |
| Schedule controls | `list schedules`, `cancel schedule: <id>`, `resume schedules` |
| Experimental sandboxed OpenCode | `build demo app` — confirm first; fails closed if sandbox/runtime checks fail |

**Mic** starts local recognition; **Stop mic** transfers the transcript to the command draft for review. **Read result** speaks a selected result locally. Voice support depends on installed on-device language assets. See [voice details](docs/VOICE.md).

Only explicitly requested workspace notes are indexed. Stale source excerpts are withheld until reindexing. Forget clears the index, not originals, task history or exported copies. Model answers are not independently verified facts. Reports are deterministic quoted-source digests, drafts are never sent, organization plans never move originals, and workers are fixed templates rather than arbitrary generated agents.

**Stop All** pauses dispatch and schedules and cancels outstanding tasks; completed effects remain. **Resume** re-enables ordinary tasks; use approved `resume schedules` to restart recurring work. Schedules pause on app restart and run only while JARVIS is open. No login startup, external accounts or messaging configured.

## Dependencies and setup

- Chat template: after opening JARVIS, run `scripts/setup-chat-model.sh` to create `jarvis-chat:4b` from existing weights.
- Existing Ollama + Qwen3 setup: [Phase 2](docs/PHASE2.md).
- Native OpenJarvis runtime: `scripts/setup-openjarvis.sh` pins source and reapplies [reviewed safety patch](patches/openjarvis-safety.patch). Requires uv and Rust; bootstrap script syntax is checked, a fresh-machine rebuild is not yet demonstrated.
- Browser: `scripts/setup-browser.sh` installs pinned Playwright/Chromium and certificate bundle into ignored `.runtime/`.
- Hermes/OpenClaw: [local agent installation](docs/LOCAL_AGENTS.md); installed separately, not granted JARVIS permissions.

`data/`, `.runtime/`, `vendor/`, `.build/` and evidence artifacts are ignored. Git alone does not transfer downloaded models or runtimes.

## Verify

```sh
./scripts/test.sh
./scripts/test-openjarvis.sh
.runtime/browser/bin/python -m unittest discover -s tests -p test_browser.py -v
python3 scripts/smoke.py
python3 scripts/smoke_extended.py
```

Tests need loopback access. Mac smoke opens Calculator/Finder. Extended smoke uses disposable notes and makes one public HTTPS request to example.com. See [status and remaining milestones](docs/STATUS.md), [API](docs/API.md), [browser](docs/BROWSER.md), and [workflows/scheduling](docs/WORKFLOWS.md).
