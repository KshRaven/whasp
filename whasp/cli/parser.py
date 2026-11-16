"""Argument parser: every `whasp <command>` and its options, grouped by area."""

from __future__ import annotations

import argparse

from .._version import __version__
from ..deploy.setup import MODES
from .commands import account, deploy, extensions, runtime, software, system

__all__ = ["build_parser"]

DESCRIPTION = (
    "Server control panel. Run `whasp` with no arguments for the terminal app; `whasp setup` makes the panel "
    "reachable (local, intranet, reverse proxy by IP, or domain with HTTPS); `whasp start` brings the website up "
    "in the background. Every screen has a command: install, catalog, svc, notes, call ..."
)


def _network_options(p: argparse.ArgumentParser) -> None:
    """Options shared by `setup` and `nginx install`."""
    p.add_argument("--domain", help="domain name to publish the panel under (proxy mode: omit it)")
    p.add_argument("--email", help="contact address for certificate notices (saved as the `email` setting)")
    p.add_argument("--certbot", action="store_true", help="get a Let's Encrypt certificate (needs --domain)")
    p.add_argument(
        "--self-signed", action="store_true", help="create a certificate for the IP / host name and serve HTTPS"
    )
    p.add_argument("--ip", help="IP address for the self-signed certificate (default: detected)")
    p.add_argument("--cert", help="path to your own certificate (with --key)")
    p.add_argument("--key", help="path to the private key for --cert")
    p.add_argument("--listen-port", type=int, help="public HTTP port nginx uses (default 80)")
    p.add_argument("--https-port", type=int, help="public HTTPS port nginx uses (default 443)")
    p.add_argument(
        "--install-packages",
        action="store_true",
        default=False,
        help="install nginx / certbot / openssl with apt when missing",
    )


def _admin_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("--admin-user", help="admin user name (when no admin exists yet)")
    p.add_argument("--admin-password", help="admin password (min 8 characters; default: ask, or generate)")
    p.add_argument("--no-prompt", action="store_true", help="never ask questions")


def _account(sp) -> None:
    p = sp.add_parser("init", help="create the config and the admin account")
    p.add_argument("--user")
    p.add_argument("--password")
    p.add_argument("--reset", action="store_true")
    p.set_defaults(f=account.cmd_init)
    p = sp.add_parser("passwd", help="change the admin password (or user name with --user)")
    p.add_argument("--user")
    p.add_argument("--password")
    p.set_defaults(f=account.cmd_passwd)
    sp.add_parser("user", help="show the admin user name").set_defaults(f=account.cmd_user)
    p = sp.add_parser("mfa", help="multi-factor status / reset / test e-mail")
    p.add_argument("action", nargs="?", default="status", choices=["status", "reset", "test-email"])
    p.add_argument("to", nargs="?")
    p.set_defaults(f=account.cmd_mfa)
    p = sp.add_parser("privacy", help="export or delete stored personal data")
    p.add_argument("action", choices=["export", "delete"])
    p.add_argument("--yes", action="store_true")
    p.set_defaults(f=account.cmd_privacy)


def _runtime(sp) -> None:
    p = sp.add_parser("web", aliases=["serve"], help="run the web panel (first run creates the admin account)")
    p.add_argument("--host")
    p.add_argument("--port", type=int)
    p.add_argument("--open", action="store_true", help="open a browser")
    p.set_defaults(f=runtime.cmd_serve)
    sp.add_parser("start", help="run the web panel in the background").set_defaults(f=runtime.cmd_start)
    sp.add_parser("stop", help="stop the background web panel").set_defaults(f=runtime.cmd_stop)
    sp.add_parser("restart", help="restart the background web panel").set_defaults(f=runtime.cmd_restart)
    sp.add_parser("url", help="print the address(es) to open in a browser").set_defaults(f=runtime.cmd_url)
    sp.add_parser("status", help="CPU / memory / disk summary").set_defaults(f=runtime.cmd_status)
    sp.add_parser("tui", help="full-screen terminal app (same as running whasp alone)").set_defaults(f=runtime.cmd_tui)
    sp.add_parser("doctor", help="diagnose setup problems").set_defaults(f=runtime.cmd_doctor)


def _deploy(sp) -> None:
    p = sp.add_parser(
        "setup", help="make the panel reachable: local, lan (intranet), proxy (by IP) or domain (with HTTPS)"
    )
    p.add_argument("--mode", choices=MODES, help="how the panel is reachable (default: ask)")
    p.add_argument("--port", type=int, help="port the panel itself listens on (default 8800)")
    p.add_argument(
        "--allow",
        action="append",
        metavar="CIDR",
        help="lan mode: only allow this address/range to sign in (repeatable)",
    )
    p.add_argument(
        "--service",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="start the panel at boot (default: yes for proxy/domain)",
    )
    _network_options(p)
    _admin_options(p)
    p.set_defaults(f=deploy.cmd_setup)
    p = sp.add_parser(
        "self-install",
        help="install Whasp system-wide from this package (/opt/whasp, /usr/local/bin) so sudo whasp works",
    )
    p.add_argument("--service", action="store_true", help="also start the panel at boot")
    _admin_options(p)
    p.set_defaults(f=deploy.cmd_self_install)
    p = sp.add_parser("service", help="start the panel at boot (install|remove|status)")
    p.add_argument("action", nargs="?", default="status", choices=["install", "remove", "status"])
    p.add_argument(
        "--system",
        action="store_true",
        help="Linux: install the system service (asks for sudo) instead of a user service",
    )
    p.add_argument("--no-start", action="store_true", help="enable at boot without starting it now")
    _admin_options(p)
    p.set_defaults(f=deploy.cmd_service)
    p = sp.add_parser("domain", help="publish the panel under a domain name (set|remove|show)")
    p.add_argument("action", nargs="?", default="show", choices=["set", "remove", "show"])
    p.add_argument("name", nargs="?")
    p.add_argument("--persist", action="store_true", help="also install the boot service")
    p.set_defaults(f=deploy.cmd_domain)
    p = sp.add_parser("nginx", help="nginx reverse proxy for the panel (install|remove|status)")
    p.add_argument("action", nargs="?", default="status", choices=["install", "remove", "status"])
    _network_options(p)
    p.set_defaults(f=deploy.cmd_nginx)


def _software(sp) -> None:
    p = sp.add_parser("install", help="install software from the catalog, e.g. whasp install nginx")
    p.add_argument("name")
    p.set_defaults(f=software.cmd_install)
    p = sp.add_parser("uninstall", help="remove software (its data is kept)")
    p.add_argument("name")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(f=software.cmd_uninstall)
    sp.add_parser("catalog", help="list installable software and what is installed").set_defaults(
        f=software.cmd_catalog
    )


def _system(sp) -> None:
    p = sp.add_parser(
        "notes", aliases=["notifications"], help="what needs your attention (security, services, installs)"
    )
    p.add_argument("-n", type=int, default=30)
    p.add_argument("--all", action="store_true", help="include already-read items")
    p.add_argument("--read", action="store_true", help="mark them read")
    p.set_defaults(f=system.cmd_notes)
    p = sp.add_parser("config", help="show/set config")
    p.add_argument("action", nargs="?", default="show", choices=["show", "set"])
    p.add_argument("key", nargs="?")
    p.add_argument("value", nargs="?")
    p.set_defaults(f=system.cmd_config)
    p = sp.add_parser("logs", help="show audit log")
    p.add_argument("-n", type=int, default=50)
    p.set_defaults(f=system.cmd_logs)


def _extensions(sp) -> None:
    sp.add_parser("ext", help="list extensions").set_defaults(f=extensions.cmd_ext)
    sp.add_parser("services", help="list managed services").set_defaults(f=extensions.cmd_services)
    p = sp.add_parser("svc", help="service action")
    p.add_argument("name")
    p.add_argument("op", choices=["start", "stop", "restart", "reload", "enable", "disable"])
    p.set_defaults(f=extensions.cmd_svc)
    p = sp.add_parser("call", help="run any extension route (k=v params)")
    p.add_argument("ext")
    p.add_argument("route")
    p.add_argument("params", nargs="*")
    p.set_defaults(f=extensions.cmd_call)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="whasp", description=DESCRIPTION)
    parser.add_argument("-V", "--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="cmd", metavar="command")
    for group in (_account, _runtime, _deploy, _software, _system, _extensions):
        group(sub)
    return parser
