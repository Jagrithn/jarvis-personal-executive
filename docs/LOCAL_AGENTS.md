# Local agent installations

Checked 2026-10-31 on macOS 27.0.1, Apple Silicon. These installations are separate from JARVIS and are not connected to its executive, task queue, permission controls, or verification system. Do not assume JARVIS supervises their actions.

## System inventory

- System Node 24.20.0, npm 11.19.0, and Python 3.14.6 are installed. OpenClaw requires a newer Node; the project-local runtime uses Node 24.22.1.
- Ollama 0.40.13 is installed, and a `qwen3:4b` model manifest is present. Its server was not running when checked.
- OpenCode CLI 1.18.30 is installed. The OpenJarvis Python environment and its Rust extension import successfully; the project-local Rust compiler is 1.99.1.
- The previously downloaded voice, browser, wake-word, scraping, MCP, and vector-search repositories are source checkouts. Their libraries were not found in the OpenJarvis virtual environment, and they are not yet enabled JARVIS features.

## Hermes Agent

Source checkout: `vendor/hermes-agent/`, revision `c419cf7c864ac0ee511dbd9f7091a8bba0b567ee`. Core dependencies were installed from its lockfile into `vendor/hermes-agent/.venv/` using system Python 3.14. This is a lean source installation, not the upstream full installer; optional browser, computer-use, desktop and provider extras may require additional setup.

Run from the JARVIS directory:

```sh
./scripts/hermes.sh --version
./scripts/hermes.sh setup
```

The wrapper stores Hermes data in ignored `data/hermes-agent/` and defaults to the installed certificate bundle for TLS. The CLI started and reported its version. No provider, messaging channel, gateway, or JARVIS integration has been configured. The setup wizard may offer network services and privileged tools; review choices before enabling them.

## OpenClaw

OpenClaw 2026.10.9 is installed under `.runtime/openclaw/` with its Node under `.runtime/node/`. Its version command succeeds. npm reported lifecycle-script approval warnings for five packages; optional features have not been verified. The wrapper uses ignored `data/openclaw/` for OpenClaw state:

```sh
./scripts/openclaw.sh --version
./scripts/openclaw.sh onboard
```

Onboarding is a separate user choice. No gateway, messaging channel, account, startup service, or JARVIS integration was configured during installation. Avoid configuring cloud providers if local-only operation is intended.

Both agents are separate programs with their own permissions. A project-local directory alone is not a sandbox and does not prevent an agent from accessing other files under your user account. Review their tool and network settings before giving them tasks.
