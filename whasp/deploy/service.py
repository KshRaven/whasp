"""Keep the panel running at boot and restart it if it stops.

  whasp service install | remove | status     systemd on Linux, Task Scheduler (SYSTEM) on Windows

As root on Linux the service runs from a dedicated runtime in /opt/whasp (see runtime.py), so it keeps working whatever
way the installing command was itself installed. Without root, a systemd user service is created instead.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from ..core import config, plat
from ..core.errors import PanelError
from .runtime import ensure_runtime, link_cli
from .system import need_root
from .system import run as _run

__all__ = ["service_control", "service_install", "service_remove", "service_status"]

TASK = "WhaspPanel"
UNIT = "/etc/systemd/system/whasp.service"
USER_UNIT = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "systemd" / "user" / "whasp.service"


def _command():
    exe = sys.executable
    return exe, {k: os.environ[k] for k in ("WHASP_HOME", "PYTHONPATH") if os.environ.get(k)}


def _systemd_quote(value):
    return '"' + str(value).replace("%", "%%").replace("\\", "\\\\").replace('"', '\\"') + '"'


def service_status():
    if plat.IS_WIN:
        rc, out = _run(["schtasks", "/query", "/tn", TASK, "/fo", "LIST"])
        if rc:
            return {"installed": False, "running": False, "kind": "Task Scheduler task " + TASK}
        return {"installed": True, "running": bool(re.search(r"Running", out)), "kind": "Task Scheduler task " + TASK}
    if not plat.has_systemd():
        return {"installed": False, "running": False, "kind": "systemd (not available here)"}
    if plat.IS_ROOT:
        en = _run(["systemctl", "is-enabled", "whasp"])[1].strip()
        act = _run(["systemctl", "is-active", "whasp"])[1].strip()
        return {
            "installed": os.path.exists(UNIT) or en in ("enabled", "disabled"),
            "running": act == "active",
            "kind": "systemd unit whasp.service",
        }
    if not USER_UNIT.exists():
        return {"installed": False, "running": False, "kind": "systemd user service whasp"}
    en = _run(["systemctl", "--user", "is-enabled", "whasp"])[1].strip()
    act = _run(["systemctl", "--user", "is-active", "whasp"])[1].strip()
    return {
        "installed": en in ("enabled", "disabled") or USER_UNIT.exists(),
        "running": act == "active",
        "kind": "systemd user service whasp",
    }


def service_install(system: bool = False, no_start: bool = False) -> dict:
    """Install the boot service. system=True on Linux elevates to root and installs the system unit."""
    if system and not plat.IS_WIN and not plat.IS_ROOT:
        need_root("Installing the system service")
    if plat.IS_WIN and not plat.IS_ROOT:
        raise PanelError("installing the boot service needs an Administrator terminal", 403)
    if not plat.IS_WIN and not plat.IS_ROOT:
        if not plat.has_systemd():
            raise PanelError("this machine has no systemd; use `whasp start` for a background process", 501)
        exe, env = _command()
        USER_UNIT.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "[Unit]",
            "Description=whasp user server control panel",
            "After=network-online.target",
            "",
            "[Service]",
            "Type=simple",
            "Environment=PYTHONUNBUFFERED=1",
        ]
        lines += [f"Environment={_systemd_quote(f'{k}={v}')}" for k, v in env.items()]
        lines += [
            f"ExecStart={_systemd_quote(exe)} -m whasp web",
            "Restart=on-failure",
            "RestartSec=3",
            "",
            "[Install]",
            "WantedBy=default.target",
            "",
        ]
        USER_UNIT.write_text("\n".join(lines), encoding="utf-8")
        _run(["systemctl", "--user", "daemon-reload"])
        rc, out = _run(["systemctl", "--user", "enable", "--now", "whasp"], 60)
        if rc:
            raise PanelError(
                out.strip()[-400:] or "systemctl --user failed; check that your user systemd manager is running", 400
            )
        return {
            "ok": True,
            "message": "Installed and started the user whasp.service. For it to start before login, enable lingering for your account (may require administrator help).",
        }
    exe, env = _command()
    if not plat.IS_WIN and plat.has_systemd():
        exe, env = ensure_runtime(), {k: v for k, v in env.items() if k == "WHASP_HOME"}
    if plat.IS_WIN:
        inner = f'"{exe}" -m whasp web'
        if env:
            inner = f'set "WHASP_HOME={env["WHASP_HOME"]}" && ' + inner
        log = str(config.LOGDIR / "server.log")
        config.LOGDIR.mkdir(parents=True, exist_ok=True)
        tr = f'cmd /s /c "{inner} >> "{log}" 2>&1"'
        rc, out = _run(
            ["schtasks", "/create", "/tn", TASK, "/tr", tr, "/sc", "onstart", "/ru", "SYSTEM", "/rl", "HIGHEST", "/f"]
        )
        if rc:
            raise PanelError(out.strip()[-400:] or "schtasks failed", 400)
        _run(["schtasks", "/run", "/tn", TASK])
        return {
            "ok": True,
            "message": f"Installed. The panel now starts at boot (task {TASK}) and runs in the background.",
        }
    if not plat.has_systemd():
        raise PanelError("this machine has no systemd; use `whasp start` for a background process", 501)
    lines = [
        "[Unit]",
        "Description=whasp server control panel",
        "After=network-online.target",
        "Wants=network-online.target",
        "",
        "[Service]",
        "Type=simple",
        "Environment=PYTHONUNBUFFERED=1",
    ]
    lines += [f"Environment={k}={v}" for k, v in env.items()]
    lines += [
        f"ExecStart={exe} -m whasp web",
        "Restart=on-failure",
        "RestartSec=3",
        "",
        "[Install]",
        "WantedBy=multi-user.target",
        "",
    ]
    with open(UNIT, "w") as f:
        f.write("\n".join(lines))
    _run(["systemctl", "daemon-reload"])
    rc, out = _run(["systemctl", "enable", *([] if no_start else ["--now"]), "whasp"], 60)
    if rc:
        raise PanelError(out.strip()[-400:] or "systemctl failed", 400)
    link = link_cli()
    return {
        "ok": True,
        "message": "Installed whasp.service"
        + ("" if no_start else " and started it")
        + ". It starts at boot and restarts if it stops."
        + (f" ({link})" if link else ""),
    }


def service_remove():
    if plat.IS_WIN and not plat.IS_ROOT:
        raise PanelError("removing the boot service needs an Administrator terminal", 403)
    if not plat.IS_WIN and not plat.IS_ROOT:
        _run(["systemctl", "--user", "disable", "--now", "whasp"], 60)
        try:
            USER_UNIT.unlink()
        except FileNotFoundError:
            pass
        _run(["systemctl", "--user", "daemon-reload"])
        return {"ok": True, "message": "User whasp.service removed."}
    if plat.IS_WIN:
        _run(["schtasks", "/end", "/tn", TASK])
        rc, out = _run(["schtasks", "/delete", "/tn", TASK, "/f"])
        if rc and "cannot find" not in out.lower() and "does not exist" not in out.lower():
            raise PanelError(out.strip()[-300:], 400)
        return {"ok": True, "message": "Boot task removed. A running panel keeps running until stopped (whasp stop)."}
    _run(["systemctl", "disable", "--now", "whasp"], 60)
    try:
        os.remove(UNIT)
    except OSError:
        pass
    _run(["systemctl", "daemon-reload"])
    return {"ok": True, "message": "whasp.service removed."}


def service_control(op):
    """start/stop the boot service (used by `whasp stop` when the panel was not started by whasp itself)."""
    if plat.IS_WIN:
        rc, out = _run(["schtasks", "/end" if op == "stop" else "/run", "/tn", TASK])
    else:
        rc, out = _run(["systemctl"] + ([] if plat.IS_ROOT else ["--user"]) + [op, "whasp"], 60)
    return rc == 0, out.strip()
