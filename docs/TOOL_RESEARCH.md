# JARVIS tool selection and local inventory

Research date: 2026-10-31. Selection is specific to the local-first JARVIS project, not a claim that any third-party project has been fully audited. Cloned source is reference material, not a new enabled capability. Do not execute installers, connect accounts, send data externally, or enable agents just because source is present.

## Available Codex skills

The following were installed globally under `~/.codex/skills/` and will be discoverable in a new Codex turn/session:

| Skill | Source | Why |
| --- | --- | --- |
| `ui-ux-pro-max` | [Next Level Builder](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill), `9a3f14f7423037ccb8feeb4fee7482291b9c820e` | Local searchable UI and accessibility guidance, including SwiftUI and cross-platform stacks. The installed SKILL.md paths were adapted for Codex; the MIT license was retained. |
| `systematic-debugging` | [Superpowers](https://github.com/obra/superpowers), `2ce8aa15d05bd57213e6f746f953aafb7ded7a8b` | Investigating build, integration, and runtime failures. |
| `verification-before-completion` | Same Superpowers revision | Require evidence for completion claims. |
| `test-driven-development` | Same Superpowers revision | Useful for security and state-transition work where tests are warranted. |
| `security-best-practices` | [OpenAI curated skills](https://github.com/openai/skills/tree/main/skills/.curated/security-best-practices) | Python and JavaScript/TypeScript security review when requested. |
| `security-threat-model` | [OpenAI curated skills](https://github.com/openai/skills/tree/main/skills/.curated/security-threat-model) | Explicit threat-model work before enabling sensitive permissions. |
| `playwright` | [OpenAI curated skills](https://github.com/openai/skills/tree/main/skills/.curated/playwright) | Browser-based interface testing; its CLI/browser dependencies may still need installation. |

Skills are instructions and supporting resources, not autonomous employees. Higher-priority instructions and the user's actual requests govern when they apply. A skill's presence does not prove its external dependencies are installed. The three OpenAI catalog skills were installed from the catalog's then-current main branch; record the repository revision on any later refresh.

The Codex marketplace confirms that the Superpowers plugin is installed. The GitHub plugin was suggested but is not installed or connected. The individually installed Superpowers skills overlap with the plugin; avoid invoking duplicate workflows for the same task.

## Downloaded source references

Ignored local checkouts, not dependencies and not bundled with the app:

| Checkout | Source revision | Purpose |
| --- | --- | --- |
| `vendor/openjarvis/` | `570d75425d50592d931bac7a17ce6b2621561c06` | Existing pinned OpenJarvis backend and desktop reference; local working changes exist and must be preserved. |
| `vendor/references/faster-whisper/` | `9e472ae9de8bb374552f531f752654554b76b2d6` | [Local transcription](https://github.com/SYSTRAN/faster-whisper) candidate for a later voice phase. |
| `vendor/references/kokoro-onnx/` | `3596b26764286a7de9d90c363e988d50578918e5` | [Local text-to-speech](https://github.com/thewh1teagle/kokoro-onnx) candidate. Review model and voice licenses separately. |
| `vendor/references/scrapling/` | `26dc85a4fa307257fb5c669c80aa44b15acb84c4` | [Web extraction](https://github.com/D4Vinci/Scrapling) candidate, only when approved browser/retrieval features are designed. |
| `vendor/references/playwright-python/` | `637cb1b859b869e796b971d7100fa02b3f17aadb` | [Python browser automation](https://github.com/microsoft/playwright-python) for isolated browser profiles and tests, phase 3. |
| `vendor/references/whisper.cpp/` | `482279b8a18855ba741d7b88c30fcb3874691f59` | [Local speech recognition](https://github.com/ggml-org/whisper.cpp), an alternative to benchmark against faster-whisper, phase 3. |
| `vendor/references/openWakeWord/` | `368c03716d1e92591906a84949bc477f3a834455` | [Wake-word detection](https://github.com/dscripka/openWakeWord), optional after push-to-talk works. Its included pretrained models have a CC BY-NC-SA 4.0 license, distinct from its Apache-2.0 code license. |
| `vendor/references/mcp-python-sdk/` | `d7845c073a2b9ba5ab2817ecf93d3e45ef24cd14` | [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) for scoped tool adapters, later phases. |
| `vendor/references/sqlite-vec/` | `04d28bd21773981e2d266bbf6aa4efbd011eb4f6` | [SQLite vector search](https://github.com/asg017/sqlite-vec), optional only if full-text search is inadequate in phase 4. |
| `vendor/references/opencode/` | `bf544cd419c5f17535c0d5af929f7ecd41188320` | [OpenCode](https://github.com/anomalyco/opencode) source for a restricted coding worker, phase 5. The CLI is not installed or connected. |

These folders are ignored by Git; moving or cloning this project elsewhere will not carry them. Retain their licenses and pin reviewed revisions if any are integrated. No voice models, browser binaries, microphone permissions, scraping services, or account access were installed/activated by this research.

## Other candidates

- **ECC and gstack:** broad development frameworks with overlapping roles. Superpowers plus Codex's existing tools are sufficient for the current phase. gstack's Codex support is experimental and its setup has additional tooling; evaluate a specific missing workflow before adding it.
- **Impeccable, Hallmark, Emil Kowalski, Scroll Craft, UI/UX Pro Max:** design workflows overlap. UI/UX Pro Max was selected for its local search and SwiftUI coverage. Impeccable and Hallmark remain useful alternatives for a specific future design pass; no need to activate competing design systems together.
- **Voice:** faster-whisper and Kokoro ONNX are candidates, not integrated features. Choose and benchmark models, memory use, latency, privacy, and distribution licenses when implementing speech. Explicitly request OS microphone access only in the product flow.
- **Web research and scraping:** existing web tools already cover research during development. Scrapling and Agent Reach are not a replacement for a JARVIS permission boundary; arbitrary pages are untrusted content. Last-30-Days is relevant only when a current-trends feature is requested.
- **Google Workspace CLI:** useful for an explicitly connected account later, but it needs account authorization, scoped permissions, and clear approval before writes. No account was connected.
- **claude-mem, OpenClaw, Hermes, and similar assistants:** separate memory/agent runtimes overlap with the existing executive and could introduce extra credential, privacy, and execution surfaces. Evaluate individual components rather than run multiple competing brains.
- **OmniRoute, free-model routers, and Headroom:** provider aggregation and compression are optional future experiments. Advertised aggregate free quotas require individual providers/accounts, vary over time, and are not guaranteed. Cloud fallback would send data off-device and must never silently replace the local default. Compression claims require workload-specific evaluation.
- **Council, Strix, reverse-engineering agents:** may be valuable for a specific review or an authorized local security assessment; model usage, external costs, and allowed targets must be scoped. Do not run offensive tooling against unapproved systems.
- **Finance/trading, gym, news, job search, study apps, SEO, Expo, Hyperframes, Adobe and writing tools:** not current JARVIS platform dependencies. Integrate individual capabilities when the user requests them, rather than expanding the baseline and resource use now.
- **Anthropic document skills:** Codex already has document, PDF, presentation, and spreadsheet skills. Some Anthropic document skills have restrictive per-skill licenses, so they were not copied.
- **Ambiguous names:** REA, Ponytail, Task Observer, Trader Skill and similar names were not installed without a reliably identified original repository and a concrete JARVIS need.

## Next development step

Finish and test the existing uncommitted OpenJarvis chat/memory integration before adding voice or other services. In particular, test safe paths, indexing approval, cancellation, real inference, packaging, and preserved macOS behavior. See `STATUS.md` and `OPENJARVIS_REVIEW.md`; current checked-out changes take precedence over older status text.
