"""Deployment commands: setup, service, domain, nginx."""

from __future__ import annotations

import sys

from ... import deploy
from ...core import config, plat
from ...core.errors import PanelError
from ...deploy.admin import ensure_admin
from ...deploy.system import elevate
from ..context import prepare_home
from ..output import c

__all__ = ["cmd_domain", "cmd_nginx", "cmd_self_install", "cmd_service", "cmd_setup"]

MENU = (
    ("local", "this machine only (127.0.0.1)"),
    ("lan", "the local network / intranet (all interfaces; optional allowed ranges and self-signed HTTPS)"),
    ("proxy", "reverse proxy on this server's IP address - no domain needed (optional self-signed HTTPS)"),
    ("domain", "reverse proxy under your domain, with a Let's Encrypt certificate if you want one"),
)


def _fail(e: PanelError):
    sys.exit(c("31", "error: ") + e.message)


def _ask(question: str, default: str = "") -> str:
    answer = input(f"{question}" + (f" [{default}]" if default else "") + ": ").strip()
    return answer or default


def _yes(question: str, default: bool = False) -> bool:
    answer = _ask(question + (" (Y/n)" if default else " (y/N)")).lower()
    return default if not answer else answer.startswith("y")


def _wizard(a) -> None:
    """Fill in the setup options by asking, for people who run plain `whasp setup`."""
    print(c("1", "How should the panel be reachable?"))
    for i, (name, text) in enumerate(MENU, 1):
        print(f"  {i}) {name:<7} {text}")
    pick = _ask("Choose 1-4", "1")
    a.mode = MENU[int(pick) - 1][0] if pick.isdigit() and 1 <= int(pick) <= 4 else pick
    if a.mode == "domain":
        a.domain = _ask("Domain name (its DNS A record must point at this server)")
        a.certbot = _yes("Get a free HTTPS certificate now (Let's Encrypt)?", True)
        if a.certbot:
            a.email = a.email or _ask("E-mail for certificate notices", config.cfg.get("email", ""))
    elif a.mode == "proxy":
        a.self_signed = _yes("Serve HTTPS with a self-signed certificate?")
    elif a.mode == "lan":
        a.self_signed = _yes("Serve HTTPS with a self-signed certificate?")
        allow = _ask("Only allow these addresses/ranges, comma separated (Enter = any)")
        a.allow = [x.strip() for x in allow.split(",") if x.strip()]
    if a.mode in ("proxy", "domain") and a.install_packages is False:
        a.install_packages = _yes("Install missing packages (nginx, certbot) with apt?", True)
    if a.service is None:
        a.service = _yes("Start the panel at boot?", True)


def cmd_setup(a):
    """whasp setup [--mode local|lan|proxy|domain] ...  Everything the panel needs to be reachable, in one step."""
    direct = a.mode in ("local", "lan") and not a.service
    if not direct and not plat.IS_WIN and not plat.IS_ROOT:
        elevate("Setup")  # re-runs this command with sudo; returns only when sudo is unavailable
    prepare_home()
    interactive = sys.stdin.isatty() and not a.no_prompt
    if not a.mode:
        if not interactive:
            sys.exit(
                "choose a mode: whasp setup --mode local|lan|proxy|domain  (or run it in a terminal for questions)"
            )
        _wizard(a)
    if a.service is None:
        a.service = a.mode in ("proxy", "domain") and not plat.IS_WIN and plat.IS_ROOT
    options = deploy.SetupOptions(
        mode=a.mode,
        port=a.port or 0,
        domain=a.domain or "",
        email=a.email or "",
        ip=a.ip or "",
        listen_port=a.listen_port or 0,
        https_port=a.https_port or 0,
        self_signed=a.self_signed,
        certbot=a.certbot,
        cert=a.cert or "",
        key=a.key or "",
        allow=a.allow or [],
        install_packages=bool(a.install_packages),
        service=bool(a.service),
        admin_user=a.admin_user or "",
        admin_password=a.admin_password or "",
        prompt=interactive,
    )
    try:
        print("\n".join(deploy.run_setup(options)))
    except PanelError as e:
        _fail(e)


def cmd_self_install(a):
    """whasp self-install  Install this package system-wide (/opt/whasp + /usr/local/bin/whasp) so `sudo whasp` works."""
    if plat.IS_WIN:
        sys.exit("self-install is for Linux. On Windows run: whasp setup   (or scripts\\install\\install.ps1)")
    if not plat.IS_ROOT:
        elevate("Installing Whasp system-wide")  # re-runs this command with sudo; returns only when sudo is unavailable
    try:
        notes = deploy.self_install()
        prepare_home()
        admin = ensure_admin(a.admin_user or "", a.admin_password or "", sys.stdin.isatty() and not a.no_prompt)
        print("\n".join(notes))
        print(f"config: {config.HOME}   files open at: {config.cfg.get('file_start')}")
        if admin["password"]:
            print(
                f"admin login created: {admin['user']} / {admin['password']}   (shown once; change it with: sudo whasp passwd)"
            )
        if a.service:
            print(deploy.service_install(system=True, no_start=False)["message"])
    except PanelError as e:
        _fail(e)
    print("Done. From now on use:  sudo whasp <command>      (start the panel: sudo whasp service install)")


def cmd_service(a):
    """whasp service install|remove|status: keep the panel running at boot (systemd / Task Scheduler)."""
    try:
        if a.action == "install":
            if a.system and not plat.IS_WIN and not plat.IS_ROOT:
                elevate("Installing the system service")
            prepare_home()
            admin = ensure_admin(a.admin_user or "", a.admin_password or "", sys.stdin.isatty() and not a.no_prompt)
            if admin["password"]:
                print(
                    f"admin login created: {admin['user']} / {admin['password']}   (shown once; change it with: whasp passwd)"
                )
            print(deploy.service_install(system=a.system, no_start=a.no_start)["message"])
        elif a.action == "remove":
            print(deploy.service_remove()["message"])
        else:
            st = deploy.service_status()
            state = (
                "installed, " + ("running" if st["running"] else "not running")
                if st["installed"]
                else "not installed (whasp service install)"
            )
            print(f"{st['kind']}: {state}")
    except PanelError as e:
        _fail(e)


def cmd_domain(a):
    """whasp domain set panel.example.com | remove | show"""
    try:
        if a.action == "set":
            if not a.name:
                sys.exit("give a domain: whasp domain set panel.example.com")
            print(deploy.set_domain(a.name)["message"])
            if a.persist:
                print(deploy.service_install()["message"])
        elif a.action == "remove":
            deploy.clear_domain()
            print("domain removed")
        else:
            info = deploy.domain_info()
            print(f"domain: {info['domain'] or '(none)'}")
            for url in info["urls"]:
                print("  ", url)
    except PanelError as e:
        _fail(e)


def cmd_nginx(a):
    """whasp nginx install|remove|status: reverse proxy for the panel (IP only, self-signed, or domain + certbot)."""
    try:
        if a.action == "install":
            prepare_home()
            print(
                "\n".join(
                    deploy.nginx_install(
                        domain=a.domain or "",
                        certbot=a.certbot,
                        email=a.email or "",
                        cert=a.cert or "",
                        key=a.key or "",
                        install_packages=a.install_packages,
                        listen_port=a.listen_port or 0,
                        https_port=a.https_port or 0,
                        self_signed=a.self_signed,
                        ip=a.ip or "",
                    )
                )
            )
        elif a.action == "remove":
            print(deploy.nginx_remove())
        else:
            for key, value in deploy.nginx_status().items():
                print(f"{key:<12} {value}")
    except PanelError as e:
        _fail(e)
