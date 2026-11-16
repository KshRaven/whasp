#!/usr/bin/env bash
# Everything that can be checked without root or network: syntax, JS syntax, unit + end-to-end tests.
set -euo pipefail
cd "$(dirname "$0")/../.."
python3 -m compileall -q whasp
if command -v node >/dev/null; then for f in whasp/web/*.js whasp/web/ui/*.js; do node --check "$f"; done; else echo "(node not found: skipping JS syntax check)"; fi
python3 -W ignore -m unittest discover -s tests -v "$@"
