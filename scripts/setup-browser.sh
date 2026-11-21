#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
python3 -m venv .runtime/browser
.runtime/browser/bin/python -m pip install --no-cache-dir 'playwright==1.58.0' 'certifi==2026.10.23'
PLAYWRIGHT_BROWSERS_PATH="$PWD/.runtime/browser-binaries" .runtime/browser/bin/python -m playwright install chromium
