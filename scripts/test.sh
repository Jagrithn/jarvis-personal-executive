#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
python3 -m unittest discover -s tests -v
