#!/bin/zsh
set -euo pipefail
ROOT="${0:A:h:h}"
export HERMES_HOME="$ROOT/data/hermes-agent"
export SSL_CERT_FILE="${SSL_CERT_FILE:-$ROOT/vendor/hermes-agent/.venv/lib/python3.14/site-packages/certifi/cacert.pem}"
exec "$ROOT/vendor/hermes-agent/.venv/bin/hermes" "$@"
