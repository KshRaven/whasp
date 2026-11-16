#!/usr/bin/env bash
# Remove whasp. Non-root removes the user install; root removes the system install.
# Keeps configuration unless --purge is given.
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then
  DATA="${XDG_DATA_HOME:-$HOME/.local/share}/whasp"
  CONF="${XDG_CONFIG_HOME:-$HOME/.config}/whasp"
  BIN="$HOME/.local/bin/whasp"
  UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
  systemctl --user disable --now whasp 2>/dev/null || true
  if [ -x "$BIN" ]; then "$BIN" stop >/dev/null 2>&1 || true; fi
  rm -f "$UNIT_DIR/whasp.service" "$BIN"
  systemctl --user daemon-reload 2>/dev/null || true
  rm -rf "$DATA"
  if [ "${1:-}" = "--purge" ]; then
    rm -rf "$CONF"
    echo "User configuration and logs removed."
  else
    echo "Kept $CONF (use --purge to delete)."
  fi
  echo "User installation removed. Restart your shell if whasp is still cached."
  exit 0
fi
systemctl disable --now whasp 2>/dev/null || true
pkill -f "python[0-9.]* -m whasp" 2>/dev/null || true   # a panel started by hand (whasp start)
rm -f /etc/systemd/system/whasp.service /usr/local/bin/whasp
systemctl daemon-reload
rm -rf /opt/whasp
if [ "${1:-}" = "--purge" ]; then rm -rf /etc/whasp; echo "Config and logs removed."; else echo "Kept /etc/whasp (use --purge to delete)."; fi
echo "whasp removed. Nginx sites, cron entries and backups it created are left in place."
