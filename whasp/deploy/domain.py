"""Publish the panel under a domain name through the Websites extension (nginx, or the built-in site host)."""

from __future__ import annotations

import re

from ..core import config
from ..core.errors import PanelError

__all__ = ["DOMAIN_RX", "clear_domain", "domain_info", "set_domain"]

DOMAIN_RX = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$|^localhost$")


def domain_info() -> dict:
    from ..server.sitehost import is_builtin

    domain = config.cfg.get("domain", "")
    base = config.cfg.get("base_path", "/whasp")
    url = f"http://{domain}:{config.cfg.get('site_port', 8080)}/" if domain and is_builtin() else f"http://{domain}/"
    local = f"http://localhost:{config.cfg['port']}{base}/"
    public = config.cfg.get("public_url", "")
    return {
        "domain": domain,
        "base_path": base,
        "port": config.cfg["port"],
        "urls": ([public] if public else []) + ([url] if domain and not public else []) + [local],
    }


def _websites():
    from ..extensions import load_extensions, registry

    if "websites" not in registry:
        load_extensions()
    ext = registry.get("websites")
    if not ext:
        raise PanelError("the Websites extension is disabled", 404)
    return ext


def set_domain(domain: str) -> dict:
    domain = str(domain or "").strip().lower()
    if not DOMAIN_RX.match(domain):
        raise PanelError("that does not look like a domain name (example: panel.example.com)")
    ext = _websites()
    old = config.cfg.get("domain", "")
    if old and old != domain:
        clear_domain()
    upstream = f"http://127.0.0.1:{int(config.cfg['port'])}"
    try:
        ext.routes["add"][0]({"domain": domain, "type": "proxy", "target": upstream, "www": False})
    except PanelError as e:
        if e.status != 409:  # 409 = the site already exists, which is fine
            raise
    config.cfg["domain"] = domain
    config.save()
    return {
        "ok": True,
        "domain": domain,
        "message": f"{domain} now forwards to the panel. Point its DNS A record at this server; the site server listens on port "
        f"{config.cfg.get('site_port', 8080)} unless nginx handles port 80. For HTTPS: whasp setup --mode domain --domain {domain} --certbot",
    }


def clear_domain() -> dict:
    domain = config.cfg.get("domain", "")
    if domain:
        try:
            _websites().routes["delete"][0]({"domain": domain})
        except PanelError:
            pass
    config.cfg["domain"] = ""
    config.save()
    return {"ok": True}
