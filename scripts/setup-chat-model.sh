#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
# The JARVIS-owned Ollama server must be running (open JARVIS first).
OLLAMA_HOST=127.0.0.1:11435 /Applications/Ollama.app/Contents/Resources/ollama create jarvis-chat:4b -f models/JarvisChat.Modelfile
