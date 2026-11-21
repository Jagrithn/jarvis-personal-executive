#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
PYTHON="$PWD/vendor/openjarvis/.venv/bin/python"
ready() {
  "$PYTHON" -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:11435/api/tags", timeout=1).read()' >/dev/null 2>&1
}
if ! ready; then
  mkdir -p artifacts/foundation-evaluation
  OLLAMA_HOST=127.0.0.1:11435 /Applications/Ollama.app/Contents/Resources/ollama serve > artifacts/foundation-evaluation/demo-ollama.log 2>&1 &
  demo_ollama_pid=$!
  trap 'kill "$demo_ollama_pid" 2>/dev/null || true' EXIT
  for attempt in {1..30}; do
    ready && break
    sleep 1
  done
  ready || { print 'Local model service did not start. See demo-ollama.log.'; exit 1; }
fi
"$PYTHON" experiments/openjarvis-evaluation/demo.py
