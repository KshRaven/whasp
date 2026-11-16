"""One-shot panel setup: pick how the panel is reachable and apply everything it needs.

local    this machine only (127.0.0.1), nothing exposed
lan      the local network / intranet: all interfaces, optional allowed address ranges, optional self-signed HTTPS
proxy    nginx reverse proxy on the server's IP address (no domain needed), optional self-signed HTTPS
domain   nginx reverse proxy under a domain name, optional Let's Encrypt certificate (certbot, with an e-mail)
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field

from ..core import config, plat
from ..core.errors import PanelError
from ..system import daemon
from . import tls
from .admin import ensure_admin
from .nginx import nginx_install
from .service import service_control, service_install
from .system import detect_ip, firewall_hint

__all__ = ["MODES", "SetupOptions", "run_setup"]

MODES = ("local", "lan", "proxy", "domain")


@dataclass
class SetupOptions:
    mode: str = "local"
    port: int = 0
    domain: str = ""
    email: str = ""
    ip: str = ""
    listen_port: int = 0
    https_port: int = 0
    self_signed: bool = False
    certbot: bool = False
    cert: str = ""
    key: str = ""
    allow: list[str] = field(default_factory=list)
    install_packages: bool = False
    service: bool = False
    admin_user: str = ""
    admin_password: str = ""
    prompt: bool = True


def _check(o: SetupOptions) -> None:
    if o.mode not in MODES:
        raise PanelError(f"mode must be one of: {', '.join(MODES)}")
    if o.mode == "domain" and not o.domain:
        raise PanelError("--mode domain needs --domain panel.example.com")
    if o.mode != "domain" and (o.domain or o.certbot):
        raise PanelError(
            "--domain and --certbot belong to --mode domain (a bare IP cannot get a Let's Encrypt certificate; use --self-signed)"
        )
    if o.mode in ("local", "lan") and (o.listen_port or o.https_port):
        raise PanelError(
            "--listen-port and --https-port are for the reverse-proxy modes (proxy, domain); use --port for the panel itself"
        )
    if o.mode == "local" and (o.allow or o.self_signed):
        raise PanelError("local mode is not reachable from other machines; use --mode lan for --allow or --self-signed")
    for item in o.allow:
        try:
            ipaddress.ip_network(item, strict=False)
        except ValueError as e:
            raise PanelError(f"--allow {item!r} is not an address or range such as 192.168.1.0/24") from e
    if o.email:
        config.validate_setting("email", o.email)


def _apply_direct(o: SetupOptions) -> list[str]:
    """local / lan: the panel listens itself."""
    notes: list[str] = []
    config.cfg.update(host="127.0.0.1" if o.mode == "local" else "0.0.0.0", trust_proxy=False, public_url="")
    if o.email:
        config.cfg["email"] = o.email
    if o.mode == "lan":
        if o.allow:
            config.cfg["allowed_ips"] = o.allow
            notes.append("only these addresses may sign in: " + ", ".join(o.allow))
        if o.self_signed:
            crt, key = tls.self_signed(o.ip or detect_ip())
            config.cfg.update(tls_cert=crt, tls_key=key)
            notes.append(f"HTTPS with a self-signed certificate ({crt}); the browser warns once")
        elif o.cert and o.key:
            config.cfg.update(tls_cert=o.cert, tls_key=o.key)
            notes.append("HTTPS with your certificate")
        else:
            notes.append(
                "plain HTTP: passwords are not encrypted on the network; add --self-signed or use mode proxy/domain"
            )
    config.save()
    return notes


def _restart(use_service: bool) -> str:
    if use_service:
        service_control("stop")
        ok, out = service_control("start")
        return "service restarted" if ok else f"could not restart the service: {out}"
    daemon.stop()
    ok, msg = daemon.start()
    return f"panel {msg}" if ok else f"could not start the panel: {msg}"


def run_setup(o: SetupOptions) -> list[str]:
    """Apply a setup and return the lines to print. Raises PanelError when something cannot be done."""
    _check(o)
    notes: list[str] = []
    admin = ensure_admin(o.admin_user, o.admin_password, o.prompt)
    if o.port:
        config.cfg["port"] = o.port
        config.save()
    if o.mode in ("local", "lan"):
        notes += _apply_direct(o)
    else:
        notes += nginx_install(
            domain=o.domain,
            certbot=o.certbot,
            email=o.email,
            cert=o.cert,
            key=o.key,
            install_packages=o.install_packages,
            listen_port=o.listen_port,
            https_port=o.https_port,
            self_signed=o.self_signed,
            ip=o.ip,
        )
    if o.service:
        notes.append(service_install(system=True)["message"])
    notes.append(_restart(o.service))

    from ..server.app import urls

    out = [f"Setup complete ({o.mode} mode).", ""]
    out += [f"  {n}" for n in notes]
    shown = (
        [config.cfg["public_url"]]
        if config.cfg.get("public_url")
        else urls(config.cfg["host"], int(config.cfg["port"]))
    )
    out += ["", "Open:"] + [f"  {u}" for u in shown]
    out.append(
        f"  username: {admin['user']}"
        + (f"   password: {admin['password']}  (shown once; change it with: whasp passwd)" if admin["password"] else "")
    )
    if o.mode == "lan":
        out.append("Firewall: " + firewall_hint([int(config.cfg["port"])]))
    if not plat.IS_WIN and not o.service:
        out.append("Start at boot: sudo whasp service install --system")
    return out
