"""HTTP routes for the web panel: /api/panel/service[/install|remove|status] and /api/panel/domain[/set|clear]."""

from __future__ import annotations

from ..core.errors import PanelError
from .domain import clear_domain, domain_info, set_domain
from .service import service_install, service_remove, service_status

__all__ = ["route"]


def route(parts: list[str], method: str, params: dict):
    if parts[0] == "service":
        step = parts[1] if len(parts) > 1 else "status"
        if step == "status":
            return service_status()
        if method != "POST":
            raise PanelError("POST required", 405)
        if step == "install":
            return service_install()
        if step == "remove":
            return service_remove()
        raise PanelError("not found", 404)
    if parts[0] == "domain":
        step = parts[1] if len(parts) > 1 else "show"
        if step == "show":
            return domain_info()
        if method != "POST":
            raise PanelError("POST required", 405)
        if step == "set":
            return set_domain(params.get("domain"))
        if step == "clear":
            return clear_domain()
    raise PanelError("not found", 404)
