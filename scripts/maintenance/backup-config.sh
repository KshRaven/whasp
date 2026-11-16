#!/usr/bin/env bash
# Archive the panel config, custom extensions/theme and audit log (contains the token HASH, keep it private).
set -euo pipefail
SRC="${WHASP_HOME:-/etc/whasp}"; DEST="${1:-$HOME/whasp-config-$(date +%F).tar.gz}"
umask 077
tar -czf "$DEST" -C "$(dirname "$SRC")" "$(basename "$SRC")"
echo "Saved $DEST"
