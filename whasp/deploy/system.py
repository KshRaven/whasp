"""Small helpers shared by the deployment modules: running commands, privilege escalation, network detection."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys

from ..core import plat
from ..core.errors import PanelError

__all__ = ["apt_install", "detect_ip", "elevate", "firewall_hint", "has_apt", "need_root", "run"]


def run(cmd: list[str], timeout: int = 120, env: dict | None = None) -> tuple[int, str]:
    """Run a command; returns (exit code, combined output). Never raises for a failing command."""
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            env=env,
            creationflags=plat.NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return 127, str(e)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def has_apt() -> bool:
    return bool(shutil.which("apt-get"))


def apt_install(packages: list[str]) -> None:
    """Install OS packages with apt (Debian/Ubuntu). Root only."""
    if not has_apt():
        raise PanelError(
            "automatic package install supports apt-based systems only; install: " + " ".join(packages), 501
        )
    env = {**os.environ, "DEBIAN_FRONTEND": "noninteractive"}
    run(["apt-get", "update", "-qq"], 300, env)
    rc, out = run(["apt-get", "install", "-y", "-qq", *packages], 900, env)
    if rc:
        raise PanelError(f"apt could not install {' '.join(packages)}: {out.strip()[-300:]}", 500)


def elevate(what: str) -> None:
    """Re-run this very command through sudo, with this interpreter and its import path, so a `pip install --user`
    copy still works for root and sudo's restricted PATH does not matter. Never returns when sudo is available."""
    if plat.IS_WIN or not shutil.which("sudo") or os.environ.get("WHASP_NO_SUDO") or os.environ.get("WHASP_ELEVATED"):
        return
    env = [f"{k}={v}" for k, v in os.environ.items() if k.startswith("WHASP_")] + ["WHASP_ELEVATED=1"]
    paths = os.pathsep.join(dict.fromkeys(p for p in sys.path if p and os.path.isdir(p)))
    print(f"{what} needs root - continuing with sudo ...", flush=True)
    os.execvp("sudo", ["sudo", "env", *env, f"PYTHONPATH={paths}", sys.executable, "-m", "whasp", *sys.argv[1:]])


def need_root(what: str) -> None:
    """Return when running as root (or Administrator); otherwise elevate or explain."""
    if plat.IS_ROOT:
        return
    elevate(what)
    who = "an Administrator terminal" if plat.IS_WIN else "root (sudo is not available)"
    raise PanelError(f"{what} needs {who}", 403)


def detect_ip() -> str:
    """The address other machines most likely use to reach this one (best effort; no traffic is sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sk:
            sk.connect(("192.0.2.1", 9))
            return sk.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def firewall_hint(ports: list[int]) -> str:
    """Commands that open the given public ports (shown after a setup; never run automatically)."""
    ports = sorted(set(ports))
    if plat.IS_WIN:
        return "; ".join(
            f'netsh advfirewall firewall add rule name="Whasp {p}" dir=in action=allow protocol=TCP localport={p}'
            for p in ports
        )
    return "; ".join(f"sudo ufw allow {p}/tcp" for p in ports)
