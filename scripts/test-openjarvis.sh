#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
exec vendor/openjarvis/.venv/bin/python -m unittest discover -s tests -p test_upstream.py -v
