# Bounded local coding worker

`coding.build` accepts only `build demo app`. The executive must obtain explicit approval before calling `execute_coding(capability, command, root, cancel)`. The adapter itself is an internal approved-action interface, not an authorization service.

The fixed work order asks installed OpenCode to generate a single passive Assignment Tracker HTML preview using `local/qwen2.5:7b` at `http://127.0.0.1:11435/v1`, capped at 1,200 output tokens. It is a real model-generated artifact, not a prewritten success template. This slice does not support arbitrary repositories, prompts, shell commands, interactive apps, or production deployment. The page explicitly describes its static-preview limitations.

## Isolation and cancellation

- Every job gets a fresh `jarvis-code-<uuid>` folder inside the approved workspace. Symlink directory components are rejected.
- OpenCode starts under macOS `sandbox-exec` with a deny-by-default policy. Its only filesystem write area is that job's `work/` (plus `/dev/null`). Controller evidence and final artifacts live in sibling `control/`, which the worker cannot write.
- Read access is restricted to required operating-system/Python/OpenCode runtime paths and this job. Only ancestor metadata needed for path resolution is exposed; personal-file contents and other workspace jobs are not allowed. The root directory itself is readable for runtime startup, without a recursive root grant.
- The only permitted network destination is the local inference port, `localhost:11435`. No inherited accounts, API keys, proxy configuration, or personal HOME/XDG directories are passed. OpenCode tools, plugins, auto-update, sharing, snapshots and project configuration are disabled as additional restrictions; the OS sandbox is the security boundary.
- A mandatory actual-process preflight proves an allowed scoped write, denied protected read/write, denied personal-home file read, denied external and wrong-loopback connection, and an available local-inference connection. Failure stops the job; there is no unsandboxed fallback.
- Cancellation, a 180-second deadline, or an oversized worker log terminates the process group. Completed/partial local job evidence remains for inspection. Logs are capped at 2 MiB by polling and rejected on read-back if oversized. This is not a disk quota for all worker runtime files.

## Independent checks

The worker returns text through OpenCode JSON events. The controller extracts HTML, rejects active elements, event handlers, external-resource attributes and URL/import/escaped CSS, and requires tracker labels and table structure. It never runs generated code or opens it in a browser. Final HTML and original worker-log hashes are stored in controller metadata. `verify_coding` independently re-reads bounded non-symlink regular files, checks metadata/hashes and the sandbox proof, re-extracts the worker output, and repeats structural checks.

These are **structural checks only**. They do not establish usability, accessibility, visual rendering, robust browser safety, factual correctness, or production reliability. The current work order intentionally omits scripts and interactive persistence. Do not silently treat generated output as trusted executable code.

## Verification

Nine focused unit tests cover structural rejection, sandbox scope, command/runtime boundaries, environment isolation, pre-start cancellation, running-process cancellation and timeout, forged/tampered output, symlinks, and failure before worker launch. On 17 November, an isolated real run using `qwen3:4b` reached Ollama but timed out after 180 seconds. The same run with `qwen2.5:7b` finished in about 19 seconds: OpenCode returned a generated HTML artifact, sandbox preflight passed, and independent artifact/log read-back matched SHA-256 `4df9fbc3f2761977e7b475838dbefbfd9084c7d6f6318a79d8e6cddab1c30854`. The disposable artifact was deleted after validation. This proves the fixed static-preview path works on this Mac, not that JARVIS can build an arbitrary runnable app.

The sandbox requires native macOS and may fail inside another restrictive sandbox. Such a failure is reported as unavailable with its concrete cause; the connector never retries without the OS boundary. A local inference process must already be listening on port 11435.

Official references consulted: [OpenCode local providers](https://opencode.ai/docs/providers/#ollama), [configuration](https://opencode.ai/docs/config/), and [permissions](https://opencode.ai/docs/permissions/). The installed `opencode run --help` was checked for the actual CLI flags.
