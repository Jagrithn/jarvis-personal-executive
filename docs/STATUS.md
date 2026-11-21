# JARVIS status — 17 November 2026

Phase 5 software-worker checkpoint: the fixed OpenCode `build demo app` path was run on the actual Mac. Qwen3 4B timed out after 180 seconds; switching the isolated worker to the already-installed Qwen2.5 7B with a 1,200-token output cap produced and independently verified a static HTML artifact in about 19 seconds. A second real run through JARVIS's task lifecycle reached `awaiting_approval`, was approved, succeeded, and retained a result and independent artifact/log hashes. This is evidence that the bounded OpenCode connection works, **not** that JARVIS can deliver a functional application or create an agent. The disposable test artifacts were removed. Full Python suite: 118 tests, nine optional skips, no failures. Native app build passes with the existing audio API deprecation warning. See `docs/CODING.md` and the new agentic milestones plan.

Phase 6 increment: registering either fixed worker now first runs it in a disposable workspace, checks its output, excludes an outside symlink, and confirms tampering is detected. A failed trial leaves the registry unchanged. The full suite now runs 118 tests with nine optional skips and no failures; native app build passes with the existing audio API deprecation warning. This is an evaluated registration gate, not a general self-building agent factory. Response-speed work remains paused at the owner's request.

Phase 5 increment: `research TOPIC and save a report` now combines Chrome search, bounded public article reading, local model summary, and a saved Markdown artifact with source URLs/hashes and independent file read-back. A live black-hole request succeeded with NASA and National Geographic URLs, a 1,769-byte report, and matching SHA-256. It took about 25 seconds. Full suite: 117 tests, nine skipped, no failures; app rebuilt. This completes one cross-domain research workflow, not the full specialist workforce or Agent Factory. Speed work is paused at the owner's request.

Voice latency follow-up: Kokoro synthesis was measured at 8.3s for a long reply versus 2.8s for a short sample. Spoken replies now use the first sentence (max 220 characters), with the complete result still displayed. Generated playback audio is cleaned up. A direct local OpenJarvis chat sample took about 3 seconds; total conversational latency will still vary with the model and task. Hands-free preference persists across app restarts. The latest app was relaunched and showed listening on; a real owner command opening Spotify appeared in history with a macOS open callback. Full Python suite remained 114 tests, nine skipped; native build passed with the known audio API deprecation warning.

Further measured improvement: ordinary greetings and clearly conversational questions now use one direct OpenJarvis OllamaEngine call, while action-like requests retain the OrchestratorAgent path. The direct bridge answered “Hi” in 2.47s in isolation. In separate actual app tests, “Hi” took 7.62s in local execution before this change, and “Hello” took 6.00s after it. These are different requests/runs, so the difference is indicative, not a controlled benchmark; the app still feels slow and needs deeper streaming/model lifecycle work. Task polling is 250ms while a reply is pending, otherwise 700ms. The latest full suite ran 115 tests, 9 skipped, no failures; native app rebuilt and the actual desktop reply was observed with automatic speech.

The note-answer path now uses qwen2.5:7b, the same model as ordinary chat and research. The app-owned Ollama service allows one loaded model, so this removes the prior chat-versus-note swap between 7B and 4B. A real indexed Obsidian answer returned a source citation in 3.52s, then 2.80s on repeat. The app was rebuilt and relaunched after this change; the 115-test suite still passed with nine skipped. No controlled end-to-end speed claim for note answers yet.

Hands-free increment: an explicit toggle starts on-device continuous recognition for “Hey Jarvis” plus a command in one utterance. It submits via existing permissions. The UI on/off and listening state were checked on the target Mac; actual spoken wake accuracy, long-running reliability, and power use remain unverified. This is not a dedicated low-power wake detector.

Interface update: the home screen now uses a muted blue-gray palette, a larger reactive core, and a hidden-by-default history panel. Quick-operation tiles are removed. The notes controls and Quit sit under More. Listening and speaking states appear on the core. A separate floating companion window with Mic and Open JARVIS was visually verified; true wake-word detection is not implemented. Native build passed; owner visual acceptance remains.

Current checkpoint: the Mac app, local executive, and bounded capabilities across Phases 0–6 are implemented, but this is still a development build rather than a general autonomous Mac assistant. Phase 4 can index the user-selected Obsidian vault and search its notes. Reindexing is manual; vault editing, backlinks, a live note graph, and general learning from all tasks remain unbuilt. The animated brain is decorative. Hermes and OpenClaw remain separate project-local installs, not integrated workers. No messaging account is connected. Distribution and cross-platform support remain in Phase 7.

Performance audit: one desktop Obsidian search took roughly 59 seconds, but the same index query completed in 0.18 seconds directly and 0.15 seconds through the local executive including verification. The discrepancy is unresolved. Knowledge-task history now records execution and verification durations. The Swift app checks model availability every eight seconds instead of every 700 milliseconds; task polling remains at 700 milliseconds. This reduces repeated model-status requests, without establishing a general latency guarantee.

Verification: the latest full Python suite ran 114 tests, 105 passed and nine optional integrations skipped. The native app builds with Swift 6.4; the audio tap API produces a macOS 27 deprecation warning. Actual desktop speed, microphone quality, and browser site behavior need owner acceptance. Historical notes below describe earlier milestones and should not be read as the current feature list.

Phase 2 desktop integration is ready for owner testing. General chat and bounded action plans use OpenJarvis and Qwen2.5 7B. The packaged executive passed real approved two-app and create/list scenarios. The owner still needs to verify the complete Swift UI interaction. Earlier evaluation-only notes below are historical.

## Latest finding: foundation evaluation supersedes earlier conversation claims

The owner subsequently reproduced conversation failures. The earlier template change below did not reliably fix them. Direct upstream-agent tests with the installed Qwen3 configurations also failed. Qwen2.5 7B has now been downloaded and passed nine bounded native OpenJarvis cases. A longer conversational demo exposed further path and factual-summary issues; revised configuration passed that conversation with verified file contents. This is an isolated acceptance demo, not an app migration or a completed general assistant. See FOUNDATION_EVALUATION.md. The existing macOS app still has its old routing/model configuration.

## Current acceptance milestone: everyday conversation

The owner requires one completed feature, automated checks, a rebuilt app, then their own test before the next milestone. See ACCEPTANCE.md. This release is awaiting owner acceptance; the full project is not complete.

Plain greetings, explanatory questions and basic follow-ups now route to chat without `chat:`. The latest three successful exchanges from the corrected conversation implementation provide bounded context. The original command remains visible in history. Exact commands and model-proposed actions retain their existing permission behavior. Conversation cannot execute tools.

Root cause addressed: the installed qwen3:4b template unconditionally prefixed an open thinking block. `models/JarvisChat.Modelfile` creates `jarvis-chat:4b` from the existing weights with an empty thinking block prefilled. Run `scripts/setup-chat-model.sh` while JARVIS/Ollama is running to recreate it. No additional model download. Prior malformed conversation outputs are excluded from new conversation context.

## Verification

- Full suite: 86 tests run, 77 passed, 9 runtime-dependent tests skipped. See artifacts/tests-conversation-full.log.
- Separate native OpenJarvis suite: 8/8 passed. See artifacts/tests-conversation-native.log (earlier run had 8 tests as well).
- Native app rebuild passed: artifacts/build-conversation.log. One macOS 27 audio API deprecation warning remains.
- Real-model acceptance: scripts/smoke_conversation.py checks greetings, compound explanatory questions, code-word recall, no drafting markup and no workspace effects. Results: artifacts/conversation-smoke.json.
- Prior combined smoke: 18 real API tasks passed, including native indexing, stale-source filtering, memory export/forget, workflow artifacts, fixed worker registration, scheduling controls and public HTTPS reading.
- User-assisted voice test: en_IN transcription reached the draft, and Open calculator executed with independent NSWorkspace evidence. Denial/offline/playback/stress tests remain outstanding.

## What exists, and limits

- Phase 0–1: native command center, authenticated executive, durable task history, scoped original actions, approvals, cancellation and independent evidence.
- Phase 2: four-action model routing; conversation fix awaiting owner acceptance. General natural-language access to all capabilities remains a separate milestone.
- Phase 3: on-device native speech and bounded static public-page reader. Full voice error-path testing and broader browser interactions remain.
- Phase 4: top-level workspace text/Markdown index, retrieval, review, export and forget. Broader selected-folder/PDF ingestion and personal-office integrations remain.
- Phase 5: deterministic workspace report/draft/organization workflows. OpenCode connector has sandbox checks and tests; a verified successful full software-build deliverable is still outstanding.
- Phase 6: fixed-template registry and recurring schedules. General agent generation, evaluation dashboard, version rollback and broader recovery remain.
- Phase 7: distribution, cross-platform UI, backup/recovery and account integrations remain.

Hermes and OpenClaw are installed only inside this project, invoked through scripts/hermes.sh and scripts/openclaw.sh. They are not global PATH commands and are not integrated workers. OpenCode is globally installed. No personal cloud, email or messaging accounts are connected.

The backend and new modules remain in the working tree; downloaded runtimes, models, data and builds are ignored and will not move with Git alone. Original supplied specifications are preserved. Tests demonstrate bounded behavior, not general autonomous task completion.
