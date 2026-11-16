"""Panel self-update: look for a newer release on PyPI and upgrade through a Tasks job.

Nothing here needs a terminal. `check` asks PyPI (at most once a day unless forced), `start_checker` repeats that in
the background and raises one notification when a newer version exists, and `plan` returns the job steps that back up
the settings, run `pip install whasp==<version>` with the interpreter the panel runs on, verify the result and restart.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import site
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

from .. import __version__
from ..core import config
from ..core.errors import PanelError
from . import notify

__all__ = ["check", "install_version", "newer", "parse", "plan", "start_checker", "status"]

PACKAGE = "whasp"
INDEX_URL = f"https://pypi.org/pypi/{PACKAGE}/json"
CHECK_EVERY = 24 * 3600  # seconds between automatic checks
_state_lock = threading.Lock()
_started = False


def _file():
    return config.HOME / "update.json"


def parse(version):
    """Sortable key for a version string: release numbers first, pre-releases (a, b, rc, dev) before the final release."""
    v = str(version or "").strip().lower().lstrip("v")
    m = re.match(r"\d+(\.\d+)*", v)
    nums = tuple(int(n) for n in m.group(0).split(".")) if m else (0,)
    pre = bool(re.search(r"\d(a|b|rc|\.?dev)\d*", v))
    return nums + (0,) * (4 - len(nums)), 0 if pre else 1


def newer(latest, current=None):
    """True when `latest` is a later release than `current` (default: the running version)."""
    return bool(latest) and parse(latest) > parse(current or __version__)


def _read():
    try:
        return json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write(d):
    try:
        config.HOME.mkdir(parents=True, exist_ok=True)
        _file().write_text(json.dumps(d), encoding="utf-8")
    except OSError:
        pass


def status():
    """What the last check found, without touching the network."""
    d = _read()
    latest = d.get("latest", "")
    return {
        "current": __version__,
        "latest": latest or __version__,
        "available": newer(latest),
        "checked": d.get("checked", 0),
        "error": d.get("error", ""),
        "auto": bool(config.cfg.get("update_check", True)),
        "url": f"https://pypi.org/project/{PACKAGE}/{latest}/" if latest else "",
    }


def _fetch():
    req = urllib.request.Request(
        INDEX_URL, headers={"User-Agent": f"{PACKAGE}/{__version__}", "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310 (fixed https URL)
        info = json.load(r)
    return str(info["info"]["version"])


def check(force=False):
    """Ask PyPI for the newest release. Cached for a day unless `force`. Network errors are reported, not raised."""
    with _state_lock:
        d = _read()
        if not force and time.time() - d.get("checked", 0) < CHECK_EVERY and not d.get("error"):
            return status()
        try:
            d.update(latest=_fetch(), checked=time.time(), error="")
        except (OSError, ValueError, KeyError, urllib.error.URLError) as e:
            d.update(checked=time.time(), error=f"could not reach PyPI ({type(e).__name__})")
        _write(d)
    st = status()
    if st["available"]:
        notify.add(
            "system",
            "info",
            f"whasp {st['latest']} is available",
            "Open Settings > Updates to install it. The panel restarts by itself afterwards.",
            key=f"update:{st['latest']}",
        )
    return st


def start_checker():
    """Daily background check (honours the `update_check` setting). Safe to call more than once."""
    global _started
    if _started:
        return
    _started = True

    def loop():
        time.sleep(60)  # let the panel finish starting
        while True:
            try:
                if config.cfg.get("update_check", True):
                    check()
            except Exception:  # a failed check must never stop the thread
                pass
            time.sleep(3600)

    threading.Thread(target=loop, daemon=True, name="update-check").start()


def _pip_argv(version):
    argv = [sys.executable, "-m", "pip", "install", "--upgrade", "--disable-pip-version-check", f"{PACKAGE}=={version}"]
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    try:
        target = site.getsitepackages()[0]
    except (AttributeError, IndexError):
        target = ""
    if not in_venv and not (target and os.access(target, os.W_OK)):
        argv.insert(4, "--user")  # per-user installs upgrade in place without sudo
    return argv


def _backup():
    src = config.CONFIG
    if not src.exists():
        return "No settings file to back up."
    dst = src.with_name(f"config.json.bak-{__version__}")
    shutil.copy2(src, dst)
    return f"Settings copied to {dst}"


def _verify(version):
    def step():
        out = subprocess.run(
            [sys.executable, "-c", f"import importlib.metadata as m;print(m.version('{PACKAGE}'))"],
            capture_output=True,
            text=True,
            timeout=60,
        ).stdout.strip()
        if out != version:
            raise PanelError(f"expected whasp {version} after the upgrade but found {out or 'nothing'}", 500)
        return f"whasp {out} is installed."

    return step


def _restart(restart):
    def step():
        threading.Timer(3.0, restart).start()
        return "Restarting the panel in a few seconds. Refresh the page if it does not reload by itself."

    return step


def install_version(version=None):
    """The version to install: the one asked for, else the newest known (checks PyPI when nothing is cached)."""
    v = str(version or "").strip()
    if not v:
        st = check(force=not status()["latest"] or status()["latest"] == __version__)
        v = st["latest"] if st["available"] else ""
    if not re.fullmatch(r"\d+(\.\d+){0,3}((a|b|rc)\d+)?(\.post\d+)?", v):
        raise PanelError("no newer version to install" if not v else "not a valid version number")
    return v


def plan(version, restart):
    """(title, steps, env) for jobs.start. `restart` is a callable that restarts the panel process."""
    if version == __version__:
        raise PanelError(f"whasp {version} is already installed", 409)
    steps = [
        _backup,
        {"cmd": [sys.executable, "-m", "ensurepip", "--upgrade"], "optional": True},
        _pip_argv(version),
        _verify(version),
        _restart(restart),
    ]
    return f"Update whasp to {version}", steps, {"PIP_NO_INPUT": "1", "PYTHONUNBUFFERED": "1"}
