# OpenJarvis foundation evaluation

This is an isolated evaluation, not a migration or production assistant. It calls the pinned upstream SimpleAgent and OrchestratorAgent directly; our keyword router and custom executive are not involved. No upstream agent loop is rewritten.

Evaluate original Qwen3 function calling, then supported structured mode with the existing chat variant. Only the upstream calculator, file_read and confirmation-required file_write tools are exposed. A before-tool governance callback narrows writes to a new fixture summary; no shell, account, browser, skill installation or personal-folder access. Scripted write approvals represent owner authorization for this disposable experiment, not an interactive approval implementation.

Record actual answers, tool results, durations, underlying response shape and independently inspected output files. Empty answers, malformed protocols, incorrect math and absent artifacts count as failures. Do not infer general reliability from a handful of passing samples. A user-facing demo follows only once a candidate passes the selected tests.

Existing application source preserved in artifacts/foundation-evaluation/before-evaluation.tar.gz; runtime data was not included or modified.

Latest results and acceptance instructions: `docs/FOUNDATION_EVALUATION.md`. Run `zsh scripts/demo-openjarvis.sh` from the project root for the native-agent demo. It uses the separately installed qwen2.5:7b, ordinary conversation, scoped calculator/file tools, and interactive write approval. It is not yet connected to the macOS app.
