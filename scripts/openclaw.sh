#!/bin/zsh
set -euo pipefail
ROOT="${0:A:h:h}"
export PATH="$ROOT/.runtime/node/node_modules/.bin:$PATH"
export OPENCLAW_STATE_DIR="$ROOT/data/openclaw"
exec "$ROOT/.runtime/openclaw/node_modules/.bin/openclaw" "$@"
