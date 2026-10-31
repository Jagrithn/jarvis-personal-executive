#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
[[ -d .build/JARVIS.app ]] || ./scripts/build.sh
open .build/JARVIS.app
