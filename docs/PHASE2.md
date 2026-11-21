# Phase 2 — local reasoning and command center

The owner authorized the interface redesign, continuation into the next build step, and installation of Ollama plus a laptop-compatible model. Phase 2 adds local intent interpretation; it does not add arbitrary tools or a general-purpose chat assistant.

## Interface

Native dark command center: cyan instrument-style status display, subtle grid, mission archive, actual active/verified/capability counts, quick-operation cards, console input, result and evidence panels, local-model availability, and explicit proposed-action confirmation. Core READY/WORKING/PAUSED/OFFLINE reflects backend state; counts are never simulated. No continuous decorative animation or GPU-heavy 3D runtime.

## Model and runtime

Ollama installed from its official macOS distribution in `/Applications/Ollama.app`. The installer could not create the optional `/usr/local/bin/ollama` shortcut without an administrator password; JARVIS uses the app executable directly, so that shortcut is unnecessary.

Model: `qwen3:4b`, Q4_K_M, approximately 2.5 GB download. Selected as a conservative first candidate for this Apple M5 / 16 GB machine. One loaded model, one parallel inference, 2048 context tokens, 180 output-token limit, temperature zero, thinking disabled, two-minute idle residency. Local inference runs at 127.0.0.1:11435 with OLLAMA_NO_CLOUD=1. Model download is the only required external transfer during setup.

The ignored `data/enable-local-model` marker enables runtime startup. JARVIS starts the official Ollama CLI when its dedicated port is unused and stops the process it owns on graceful exit. An existing runtime on that port is reused and not terminated. Unexpected hard termination can leave an Ollama process available for reuse; no login item is installed.

## Routing and authorization

1. Exact documented commands use the deterministic path with no model invocation.
2. Other commands enter the same serialized queue and a cancellable local inference process. A deterministic preflight refuses compound/negated requests rather than asking the model to silently choose one part.
3. Structured output must contain exactly `capability` (four allowlisted IDs or `none`) and a bounded `reason`. The model cannot supply file paths, tools, scripts, permissions, or tool parameters.
4. `none`, unavailable models, malformed responses, and timeouts fail safely with no action.
5. A valid interpretation creates `awaiting_approval`, with the proposed action and scope visible. It performs no side effect until the owner clicks Confirm action. Reject and Stop All cancel pending proposals.
6. Confirmation revalidates scope and queues the fixed adapter. Existing independent verification still determines success. Double confirmation is rejected, preventing duplicate execution.

Classification can be wrong even with valid JSON; confirmation is intentionally required for model-selected actions. This does not alter the immediate behavior of explicit supported commands.

## API additions

`GET /v1/model`: enabled, model, status, available, installed, local_only.

`POST /v1/tasks/{id}/approve` with `{}`: valid only for awaiting_approval while dispatch is enabled. Uses the same launch-token authentication. Task records add nullable `proposal` (capability/reason/metrics) and `requested_path`. Existing task records remain decodable; no SQLite schema change is needed. Pending proposals become interrupted after restart rather than silently executing.

Run `./scripts/test.sh` for deterministic and fake-model regressions. Run `python3 scripts/benchmark_model.py` while the enabled JARVIS runtime is running for 20 actual model requests, schema validation, latency, token speed and loaded-model memory evidence. It never approves or executes any model proposal.

Sources checked during implementation:
- https://docs.ollama.com/macos
- https://ollama.com/library/qwen3:4b
- https://docs.ollama.com/api/chat
- https://docs.ollama.com/capabilities/structured-outputs

## Reproduce the local model setup

After installing the official Ollama app (a third-party executable installation requiring owner authorization), from the project root:

```sh
mkdir -p data
touch data/enable-local-model
./scripts/build.sh
./scripts/run.sh
OLLAMA_HOST=127.0.0.1:11435 /Applications/Ollama.app/Contents/Resources/ollama pull qwen3:4b
python3 scripts/benchmark_model.py
python3 scripts/smoke_reasoning.py
```

The pull downloads approximately 2.5 GB. Keep the JARVIS app running during the benchmark; it owns the local runtime. Quit stops a runtime it started. To disable local reasoning, remove only the empty `data/enable-local-model` marker and restart JARVIS; exact commands remain functional.

The final measured candidate passes 20/20 guarded routing checks. This establishes suitability for the current four-capability prototype; it does not establish that 4B is the smallest possible viable model or that it can perform general autonomous work.

## Conversation correction — 1 November 2026

Plain questions and greetings now route directly to text conversation. The original action classifier still proposes only the four initial capabilities. `chat:` remains an explicit fallback for other wording. Conversation includes up to three prior successful corrected chat exchanges; old drafting-text outputs are excluded.

The local qwen3:4b template inspected on this machine always opened `<think>`. The chat-specific `jarvis-chat:4b` template prefills an empty thinking block using the same weights. Recreate with `scripts/setup-chat-model.sh` after opening JARVIS. Qwen documents the distinction between hard template control and the soft `/no_think` instruction: https://qwen.readthedocs.io/en/stable/getting_started/quickstart.html . The real-model smoke suite tests concise final answers, not merely successful HTTP responses.
