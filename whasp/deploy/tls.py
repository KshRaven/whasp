"""Certificates: self-signed ones for an IP or host name, and Let's Encrypt through certbot."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from ..core import config
from ..core.errors import PanelError
from .system import run

__all__ = ["certbot", "self_signed", "tls_dir"]


def tls_dir() -> Path:
    path = config.HOME / "tls"
    path.mkdir(parents=True, exist_ok=True)
    return path


def self_signed(host: str) -> tuple[str, str]:
    """Create (or reuse) a self-signed certificate for an IP or host name. Browsers warn once until it is trusted."""
    if not shutil.which("openssl"):
        raise PanelError(
            "openssl not found. Install it (Linux: sudo apt install openssl) or pass --install-packages", 501
        )
    folder = tls_dir()
    safe = re.sub(r"[^A-Za-z0-9.-]", "_", host)
    crt, key = folder / f"{safe}.crt", folder / f"{safe}.key"
    if not (crt.exists() and key.exists()):
        san = f"IP:{host}" if re.fullmatch(r"[0-9.]+|[0-9a-fA-F:]+", host) else f"DNS:{host}"
        rc, out = run(
            [
                "openssl",
                "req",
                "-x509",
                "-nodes",
                "-newkey",
                "rsa:2048",
                "-days",
                "825",
                "-keyout",
                str(key),
                "-out",
                str(crt),
                "-subj",
                f"/CN={host}",
                "-addext",
                f"subjectAltName={san}",
            ]
        )
        if rc:
            raise PanelError("openssl failed: " + out.strip()[-300:], 500)
        try:
            os.chmod(key, 0o600)
        except OSError:
            pass
    return str(crt), str(key)


def certbot(domain: str, email: str) -> str:
    """Request a certificate for `domain` through certbot's nginx plugin and let it add the HTTPS redirect."""
    if not shutil.which("certbot"):
        raise PanelError(
            "certbot not found: sudo apt install certbot python3-certbot-nginx (or pass --install-packages)", 501
        )
    cmd = ["certbot", "--nginx", "-d", domain, "--non-interactive", "--agree-tos", "--redirect"]
    cmd += ["-m", email] if email else ["--register-unsafely-without-email"]
    rc, out = run(cmd, 300)
    if rc:
        raise PanelError(
            "certbot failed (does the domain's DNS point at this server, and is port 80 reachable?):\n"
            + out.strip()[-500:],
            500,
        )
    return "HTTPS enabled by certbot (renewal is installed by the certbot package)."
