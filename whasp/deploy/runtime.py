"""The dedicated Linux runtime: a root-owned virtual environment in /opt/whasp that the boot service runs from."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from .._version import __version__
from ..core.errors import PanelError
from .system import apt_install, run

__all__ = ["APP_DIR", "base_python", "ensure_runtime", "link_cli", "self_install"]

APP_DIR = Path("/opt/whasp")
BIN_LINK = Path("/usr/local/bin/whasp")


def base_python() -> str:
    """A Python the service can rely on: never one that lives in a home folder."""
    for cand in (sys.executable, shutil.which("python3") or "", "/usr/bin/python3"):
        if cand and os.path.exists(cand) and not os.path.realpath(cand).startswith(("/home/", "/root/")):
            return cand
    raise PanelError(
        "no system-wide Python found (only copies inside home folders). Install one: sudo apt install python3 python3-venv",
        500,
    )


def ensure_runtime() -> str:
    """Create or refresh /opt/whasp (a venv with this same Whasp version) and return its python."""
    vpy = APP_DIR / "bin" / "python"
    if not vpy.exists():
        print(f"creating {APP_DIR} ...", flush=True)
        APP_DIR.mkdir(parents=True, exist_ok=True)
        base = base_python()
        rc, out = run([base, "-m", "venv", str(APP_DIR)])
        if rc and shutil.which("apt-get"):
            print("venv module missing - installing python3-venv ...", flush=True)
            apt_install(["python3-venv"])
            rc, out = run([base, "-m", "venv", str(APP_DIR)])
        if rc or not vpy.exists():
            raise PanelError(f"could not create {APP_DIR}: {out.strip()[-300:]}", 500)
    src = Path(__file__).resolve().parents[2]
    targets = [str(src)] if (src / "pyproject.toml").is_file() else [f"whasp=={__version__}", "whasp"]
    print("installing Whasp into the service environment ...", flush=True)
    out = ""
    for target in targets:
        rc, out = run([str(vpy), "-m", "pip", "install", "--quiet", "--upgrade", target], 600)
        if rc == 0:
            return str(vpy)
    raise PanelError("pip could not install Whasp into the service environment:\n" + out[-600:], 500)


def link_cli() -> str:
    """/usr/local/bin/whasp -> the service environment, so plain `sudo whasp ...` always works."""
    src = APP_DIR / "bin" / "whasp"
    if not src.exists():
        return ""
    if BIN_LINK.is_symlink() or not BIN_LINK.exists():
        if BIN_LINK.is_symlink():
            BIN_LINK.unlink()
        BIN_LINK.symlink_to(src)
        return f"command {BIN_LINK} (works with sudo)"
    return ""


def self_install() -> list[str]:
    """Install Whasp for the whole system from this very package, so it no longer depends on one user's pip scope.

    Creates the root-owned runtime in /opt/whasp, links `whasp` into /usr/local/bin (so `sudo whasp ...` is found
    whatever sudo's PATH is) and returns lines describing what was done."""
    if not sys.platform.startswith("linux"):
        raise PanelError(
            "self-install is for Linux; on Windows run: whasp setup  (or scripts\\install\\install.ps1)", 501
        )
    py = ensure_runtime()
    notes = [f"runtime: {APP_DIR} ({py})"]
    link = link_cli()
    notes.append(link or f"command: {BIN_LINK} already exists and was left as it is")
    return notes
