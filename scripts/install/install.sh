#!/usr/bin/env bash
# whasp installer for Debian/Ubuntu (Windows: install.ps1; run from scripts/install). Non-root installs are user-local.
# Usage: bash install.sh [--user] [--port 8800] [--with "nginx ufw fail2ban"]
set -euo pipefail

PREFIX=/opt/whasp; CONF=/etc/whasp; PORT=8800; WITH=""; USER_INSTALL=0
while [ $# -gt 0 ]; do
  case "$1" in
    --port) PORT="$2"; shift 2;;
    --with) WITH="$2"; shift 2;;
    --user) USER_INSTALL=1; shift;;
    -h|--help) sed -n '1,3p' "$0"; exit 0;;
    *) echo "unknown option: $1" >&2; exit 2;;
  esac
done

SRC="$(cd "$(dirname "$0")/../.." && pwd)"

if [ "$USER_INSTALL" -eq 1 ] || [ "$(id -u)" -ne 0 ]; then
  [ -z "$WITH" ] || { echo "--with installs operating-system packages; use the system installer with sudo for that." >&2; exit 2; }
  PYTHON="$(command -v python3 || command -v python || true)"
  [ -n "$PYTHON" ] || { echo "Python 3.9+ is required; install it for your user or ask the server administrator." >&2; exit 1; }
  "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else "Python 3.9+ is required")'

  DATA="${XDG_DATA_HOME:-$HOME/.local/share}/whasp"
  CONF="${XDG_CONFIG_HOME:-$HOME/.config}/whasp"
  BIN="$HOME/.local/bin"
  WRAPPER="$BIN/whasp"
  echo "==> Installing Whasp for $USER"
  mkdir -p "$DATA/src" "$CONF" "$BIN" "$HOME/www"
  rm -rf "$DATA/src"
  mkdir -p "$DATA/src"
  cp -a "$SRC/." "$DATA/src/"
  rm -rf "$DATA/src/.git" "$DATA/src/.dev-home" "$DATA/src/__pycache__"

  "$PYTHON" - "$WRAPPER" "$PYTHON" "$DATA/src" "$CONF" <<'PY'
import shlex, sys

wrapper, python, source, config = sys.argv[1:]
with open(wrapper, "w", encoding="utf-8") as f:
    f.write("#!/bin/sh\n")
    f.write("export WHASP_HOME=" + shlex.quote(config) + "\n")
    f.write("export PYTHONPATH=" + shlex.quote(source) + "\n")
    f.write("exec " + shlex.quote(python) +
            " -c 'import sys; sys.argv[0]=\"whasp\"; sys.path[:]=[p for p in sys.path if p]; from whasp.cli import main; main()' \"$@\"\n")
PY
  chmod 755 "$WRAPPER"

  for rc in "$HOME/.profile" "$HOME/.bashrc" "$HOME/.zshenv"; do
    mkdir -p "$(dirname "$rc")"
    if [ ! -f "$rc" ] || ! grep -Fq "# Added by Whasp installer" "$rc"; then
      cat >> "$rc" <<'PATH_EOF'
# Added by Whasp installer
case ":$PATH:" in
  *:"$HOME/.local/bin":*) ;;
  *) export PATH="$HOME/.local/bin:$PATH" ;;
esac
PATH_EOF
    fi
  done

  "$WRAPPER" init
  "$WRAPPER" config set port "$PORT" >/dev/null
  echo
  echo "Done. Whasp is installed for your user; no sudo was used."
  echo "Run: $WRAPPER start"
  echo "Open a new shell (or run: export PATH=\"$HOME/.local/bin:\$PATH\") to use: whasp"
  echo "Optional user service: whasp service install (systemd user manager; no sudo)"
  echo "For a public domain, point DNS here and use whasp domain set NAME; ports 80/443 or a reverse proxy need separate server configuration."
  exit 0
fi

[ "$(id -u)" -eq 0 ] || { echo "Run as root for a system install, or use --user." >&2; exit 1; }
command -v apt-get >/dev/null || { echo "This script supports apt-based systems only. See README for a manual install." >&2; exit 1; }
command -v systemctl >/dev/null || { echo "systemd is required." >&2; exit 1; }

echo "==> Installing system packages (python3 $WITH)"
apt-get update -qq
# shellcheck disable=SC2086
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 $WITH
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else "Python 3.9+ is required")'

echo "==> Copying files to $PREFIX"
rm -rf "$PREFIX/src"; mkdir -p "$PREFIX"
cp -a "$SRC" "$PREFIX/src"
rm -rf "$PREFIX/src/.git" "$PREFIX/src/.dev-home"

echo "==> Creating the whasp command"
cat > /usr/local/bin/whasp <<WRAP
#!/bin/sh
# Config lives in $CONF (root only): other users are re-run through sudo automatically.
# The -c form (instead of -m) avoids importing an ./whasp folder from the current directory.
export WHASP_HOME=$CONF
export PYTHONPATH=$PREFIX/src
if [ "\$(id -u)" -ne 0 ] && [ ! -r "$CONF/config.json" ] && command -v sudo >/dev/null 2>&1; then
  exec sudo env WHASP_HOME="$CONF" PYTHONPATH="$PREFIX/src" /usr/bin/python3 -c 'import sys; sys.argv[0]="whasp"; sys.path[:]=[p for p in sys.path if p]; from whasp.cli import main; main()' "\$@"
fi
exec /usr/bin/python3 -c 'import sys; sys.argv[0]="whasp"; sys.path[:]=[p for p in sys.path if p]; from whasp.cli import main; main()' "\$@"
WRAP
chmod 755 /usr/local/bin/whasp

echo "==> Initialising config in $CONF (the admin password is shown once)"
whasp init
whasp config set port "$PORT" >/dev/null

echo "==> Installing systemd unit"
install -m 644 "$PREFIX/src/contrib/systemd/whasp.service" /etc/systemd/system/whasp.service
systemctl daemon-reload
systemctl enable --now whasp
sleep 1

echo
whasp doctor || true
echo
echo "Done. The panel is running as the 'whasp' service on port $PORT (all interfaces)."
echo "Restrict it to this machine with:  whasp config set host 127.0.0.1   (then: systemctl restart whasp)"
echo "Put it behind HTTPS before exposing it to the internet: see contrib/nginx/whasp.conf.example and docs/SECURITY.md"
echo "Change the password any time with 'whasp passwd'. Turn on a second factor in Settings, or run 'whasp mfa'."
