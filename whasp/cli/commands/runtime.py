"""Run the panel: web, start, stop, restart, url, status, tui, doctor."""

from __future__ import annotations

import socket
import sys
import time

from ...auth import mfa
from ...core import config, plat
from ...extensions import load_extensions, registry
from ...system import daemon, monitor
from ..context import ensure_admin
from ..output import bar, c, size

__all__ = ["cmd_doctor", "cmd_restart", "cmd_serve", "cmd_start", "cmd_status", "cmd_stop", "cmd_tui", "cmd_url"]


def cmd_serve(a):
    from ...server.app import serve

    ensure_admin()
    if getattr(a, "host", None):
        config.cfg["host"] = a.host
    if getattr(a, "port", None):
        config.cfg["port"] = a.port
    if getattr(a, "open", False):
        import threading
        import webbrowser

        from ...server.app import urls

        threading.Timer(
            1.5,
            lambda: webbrowser.open(
                urls(
                    "127.0.0.1" if config.cfg["host"] in ("0.0.0.0", "::") else config.cfg["host"],
                    int(config.cfg["port"]),
                )[0]
            ),
        ).start()
    serve()


def cmd_start(a):
    """Run the web panel in the background (no systemd or service needed)."""
    from ...server.app import urls

    ensure_admin()
    ok, msg = daemon.start()
    print(("" if ok else c("31", "error: ")) + f"web panel: {msg}")
    if ok:
        for u in urls(config.cfg["host"], int(config.cfg["port"])):
            print("  open", u)
        print(f"  user: {config.cfg['admin']['username']}   (forgot the password? whasp passwd)")
    sys.exit(0 if ok else 1)


def cmd_stop(a):
    ok, msg = daemon.stop()
    print(("" if ok else c("31", "error: ")) + f"web panel: {msg}")
    sys.exit(0 if ok else 1)


def cmd_restart(a):
    daemon.stop()
    cmd_start(a)


def cmd_url(a):
    from ...server.app import urls

    for u in urls(config.cfg["host"], int(config.cfg["port"])):
        print(u)


def cmd_status(a):
    m = monitor.Monitor()
    time.sleep(0.6)
    s, mem, info = m.sample(), monitor.meminfo(), monitor.system_info()
    print(
        c("1", f"{info['hostname']}")
        + f"  {info['os']}  {'build' if plat.IS_WIN else 'kernel'} {info['kernel']}  up {info['uptime'] // 3600}h"
    )
    la = monitor.loadavg()
    print(
        f"CPU    {bar(s['cpu'])} {s['cpu']:5.1f}%  "
        + (f"load {la[0]:.2f}/{info['cpus']}" if la else f"{info['cpus']} CPUs")
    )
    print(f"Memory {bar(s['mem'])} {s['mem']:5.1f}%  {size(mem['used'])} / {size(mem['total'])}")
    for d in monitor.disks():
        p = 100 * d["used"] / d["total"] if d["total"] else 0
        print(f"Disk   {bar(p)} {p:5.1f}%  {d['mount']}  {size(d['used'])} / {size(d['total'])}")
    from ...server.app import urls

    up = daemon.listening()
    print(
        f"Web    {c('32', 'running') if up else c('33', 'stopped')}  "
        + (urls(config.cfg["host"], int(config.cfg["port"]))[0] if up else "start it with: whasp start")
    )


def cmd_tui(a):
    ensure_admin()
    try:
        from ...tui import main as tui
    except ImportError:
        sys.exit(
            "The terminal app needs curses. Windows: pip install windows-curses (pip install . does this for you). Or use: whasp status / whasp web"
        )
    tui()


def cmd_doctor(a):
    bad = 0

    def line(ok, msg):
        nonlocal bad
        bad += ok is False
        print({True: c("32", "[ ok ]"), False: c("31", "[FAIL]"), None: c("33", "[warn]")}[ok], msg)

    line(sys.version_info >= (3, 9), f"Python {sys.version.split()[0]} (need 3.9+) on {monitor.system_info()['os']}")
    line(config.CONFIG.exists(), f"config file {config.CONFIG}")
    if config.CONFIG.exists():
        priv = plat.perms_private(config.CONFIG)
        line(
            True if priv is None else priv,
            "config permissions are private (0600)"
            if priv is not None
            else "config folder ACL is set by `whasp init` (inspect with: icacls " + str(config.HOME) + ")",
        )
    line(config.has_admin(), "admin account is set" if config.has_admin() else "no admin account yet: run whasp init")
    line(
        True if mfa.required() else None,
        "multi-factor sign-in is on (" + ", ".join(mfa.methods()) + ")"
        if mfa.required()
        else "multi-factor sign-in is off (enable it in Settings)",
    )
    tls = bool(config.cfg["tls_cert"] and config.cfg["tls_key"])
    loop = config.cfg["host"] in ("127.0.0.1", "::1", "localhost")
    line(
        True if (loop or tls) else None,
        f"bind {config.cfg['host']}:{config.cfg['port']} ({'TLS' if tls else 'plain HTTP: passwords are not encrypted; use HTTPS or host=127.0.0.1'})",
    )
    who = "Administrator" if plat.IS_WIN else "root"
    line(
        None if not config.IS_ROOT else True,
        f"running as {who} (needed to manage services, firewall, scheduled tasks)"
        if config.IS_ROOT
        else f"not {who}: service/firewall/nginx actions will fail",
    )
    with socket.socket() as s:
        s.settimeout(0.5)
        up = s.connect_ex((("127.0.0.1" if loop else config.cfg["host"]), int(config.cfg["port"]))) == 0
    line(True, "server is " + ("listening" if up else "not running"))
    load_extensions()
    for e in sorted(registry.values(), key=lambda e: e.name):
        line(
            True if e.available else None,
            f"extension {e.name}" + ("" if e.available else f" (missing: {', '.join(e.missing)})"),
        )
    sys.exit(1 if bad else 0)
