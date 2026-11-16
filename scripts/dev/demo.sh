#!/usr/bin/env bash
# Try every feature in a throwaway sandbox: separate config folder, e-mail codes printed to this terminal.
# Usage: scripts/dev/demo.sh [port]      Then: Settings -> Multi-factor sign-in -> E-mail codes -> any address.
set -euo pipefail
cd "$(dirname "$0")/../.."
export WHASP_HOME="$(mktemp -d)" WHASP_DEV=1 PORT="${1:-8800}"
python3 -m whasp init
python3 -m whasp config set port "$PORT" >/dev/null
python3 -m whasp config set smtp '{"host":"console","from":"demo@localhost"}' >/dev/null
python3 -m whasp config set operator '{"name":"Demo operator","email":"you@example.com","address":""}' >/dev/null
[ "${BIND_ALL:-}" = 1 ] && python3 -m whasp config set host 0.0.0.0 >/dev/null   # used by the Docker demo only
echo "Open http://127.0.0.1:$PORT  | sandbox: $WHASP_HOME | Ctrl+C to stop"
exec python3 -m whasp serve
