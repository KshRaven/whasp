"""Publish the panel through an nginx reverse proxy: by IP address (no domain needed), with a self-signed
certificate, or under a domain with a Let's Encrypt certificate."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from ..core import config, plat
from ..core.errors import PanelError
from . import tls
from .system import apt_install, detect_ip, firewall_hint, need_root, run

__all__ = ["nginx_install", "nginx_remove", "nginx_status", "render_nginx"]

AVAILABLE = Path("/etc/nginx/sites-available")
ENABLED = Path("/etc/nginx/sites-enabled")
CONFD = Path("/etc/nginx/conf.d")
SITE_NAME = "whasp-panel.conf"
HOST_RX = re.compile(r"^[A-Za-z0-9.-]+$")


def render_nginx(
    domain: str = "",
    port: int = 8800,
    cert: str = "",
    key: str = "",
    listen_port: int = 0,
    https_port: int = 0,
) -> str:
    """Server block for the panel. Without cert/key it serves plain HTTP; with both it serves HTTPS and redirects
    HTTP to it. No domain = IP mode: the block answers for any host name, so http://SERVER-IP[:port]/ works.
    listen_port / https_port are the PUBLIC ports nginx listens on (default 80 / 443)."""
    if domain and not HOST_RX.match(domain):
        raise PanelError("the domain may only contain letters, digits, dots and dashes")
    default = " default_server" if not domain else ""
    name = domain or "_"
    http, https = listen_port or 80, https_port or 443
    proxy = f"""\
    client_max_body_size 0;                  # uploads are limited by the panel, not by nginx

    location / {{
        proxy_pass http://whasp_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $whasp_conn_upgrade;
        proxy_buffering off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }}
"""
    head = f"""\
# Managed by `whasp nginx install` - safe to edit; running it again overwrites this file.
upstream whasp_backend {{
    server 127.0.0.1:{port};
    keepalive 16;
}}

map $http_upgrade $whasp_conn_upgrade {{
    default upgrade;
    ''      close;
}}

"""
    if cert and key:
        tail = "" if https == 443 else f":{https}"
        return (
            head
            + f"""\
server {{
    listen {http}{default};
    listen [::]:{http}{default};
    server_name {name};
    location /.well-known/acme-challenge/ {{ root /var/www/html; }}
    location / {{ return 301 https://$host{tail}$request_uri; }}
}}

server {{
    listen {https} ssl{default};
    listen [::]:{https} ssl{default};
    server_name {name};

    ssl_certificate     {cert};
    ssl_certificate_key {key};
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_cache shared:whasp_ssl:10m;
    add_header Strict-Transport-Security "max-age=31536000" always;

{proxy}}}
"""
        )
    return (
        head
        + f"""\
server {{
    listen {http}{default};
    listen [::]:{http}{default};
    server_name {name};

{proxy}}}
"""
    )


def _paths() -> tuple[Path, Path | None]:
    if AVAILABLE.is_dir() and ENABLED.is_dir():  # Debian/Ubuntu layout
        return AVAILABLE / SITE_NAME, ENABLED / SITE_NAME
    return CONFD / SITE_NAME, None  # RHEL/Alpine/other layout


def _reload() -> None:
    rc, out = run(["nginx", "-t"])
    if rc:
        raise PanelError("nginx rejected the config:\n" + out.strip()[-500:], 500)
    if shutil.which("systemctl"):
        run(["systemctl", "reload", "nginx"])
    else:
        run(["nginx", "-s", "reload"])


def nginx_install(
    domain: str = "",
    certbot: bool = False,
    email: str = "",
    cert: str = "",
    key: str = "",
    install_packages: bool = False,
    listen_port: int = 0,
    https_port: int = 0,
    self_signed: bool = False,
    ip: str = "",
) -> list[str]:
    """Write the panel's nginx site and point the panel at it. Returns human-readable notes.
    No domain = IP mode; --certbot needs a real domain, --self-signed works for an IP."""
    if plat.IS_WIN:
        raise PanelError(
            "this reverse-proxy setup targets Linux; on Windows use the Websites page or the built-in site server", 501
        )
    need_root("Installing the nginx site")
    if certbot and not domain:
        raise PanelError(
            "--certbot needs a domain name (Let's Encrypt cannot certify a bare IP). Add --domain, or use --self-signed"
        )
    if self_signed and (cert or key):
        raise PanelError("use either --self-signed or --cert/--key, not both")
    if bool(cert) != bool(key):
        raise PanelError("--cert and --key go together")
    if install_packages:
        apt_install(
            ["nginx", *(["certbot", "python3-certbot-nginx"] if certbot else []), *(["openssl"] if self_signed else [])]
        )
    if not shutil.which("nginx"):
        raise PanelError(
            "nginx not found. Install it: sudo apt install nginx"
            + (" certbot python3-certbot-nginx" if certbot else "")
            + " (or pass --install-packages)",
            501,
        )
    host_ip = ip or ("" if domain else detect_ip())
    if self_signed:
        cert, key = tls.self_signed(domain or host_ip)
    available, enabled = _paths()
    notes: list[str] = []
    stock = ENABLED / "default"
    if (
        not domain and (listen_port or 80) == 80 and stock.is_symlink()
    ):  # the stock "Welcome to nginx" site owns port 80
        stock.unlink()
        notes.append(
            "disabled nginx's stock 'default' site (it owned port 80); restore: sudo ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/"
        )
    port = int(config.cfg["port"])
    available.write_text(render_nginx(domain, port, cert, key, listen_port, https_port), encoding="utf-8")
    if enabled is not None:
        if enabled.is_symlink() or enabled.exists():
            enabled.unlink()
        enabled.symlink_to(available)
    _reload()
    notes.insert(0, f"nginx site written: {available}")

    email = email or config.cfg.get("email", "")
    if certbot:
        notes.append(tls.certbot(domain, email))
        if not email:
            notes.append(
                "No e-mail set: certbot registered without one (no expiry notices). Add it later: whasp config set email you@example.com"
            )
    elif domain:
        notes.append(
            f"HTTP only so far. Add HTTPS: whasp nginx install --domain {domain} --certbot --email you@example.com"
        )

    http, https = listen_port or 80, https_port or 443
    secure = bool(cert and key) or certbot
    scheme, public = ("https", https) if secure else ("http", http)
    shown = (
        f"{scheme}://{domain or host_ip}"
        + ("" if (scheme, public) in (("http", 80), ("https", 443)) else f":{public}")
        + "/"
    )
    config.cfg.update(host="127.0.0.1", trust_proxy=True, public_url=shown)
    if domain:
        config.cfg["domain"] = domain
    if email:
        config.cfg["email"] = email
    config.save()
    notes.append(
        f"panel now listens on 127.0.0.1:{port} only and trusts the proxy (restart it once: whasp restart, or systemctl restart whasp)"
    )
    notes.append(
        f"Open: {shown}"
        + (
            f"  (self-signed certificate: the browser warns once; trust the .crt in {tls.tls_dir()} on your devices)"
            if self_signed
            else ""
        )
    )
    if not domain:
        notes.append(
            "No domain: behind a router/NAT or a cloud firewall, forward/open the port above and use the PUBLIC IP."
        )
    notes.append("Firewall: " + firewall_hint([http, https] if secure else [http]))
    return notes


def nginx_remove() -> str:
    need_root("Removing the nginx site")
    available, enabled = _paths()
    if enabled is not None and (enabled.is_symlink() or enabled.exists()):
        enabled.unlink()
    available.unlink(missing_ok=True)
    if shutil.which("nginx") and run(["nginx", "-t"])[0] == 0:
        _reload()
    config.cfg.update(public_url="", trust_proxy=False)
    config.save()
    return "nginx site removed (certificates, if any, stay in /etc/letsencrypt). Set host to 0.0.0.0 to reach the panel directly again."


def nginx_status() -> dict:
    available, _ = _paths()
    return {
        "nginx": bool(shutil.which("nginx")),
        "site": str(available) if available.exists() else "",
        "public_url": config.cfg.get("public_url", ""),
        "trust_proxy": bool(config.cfg.get("trust_proxy")),
    }
