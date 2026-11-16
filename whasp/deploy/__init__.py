"""Run the panel persistently and publish it: boot service, domain, nginx reverse proxy, certificates, setup modes."""

from __future__ import annotations

from . import setup as setup
from .api import route
from .domain import clear_domain, domain_info, set_domain
from .nginx import nginx_install, nginx_remove, nginx_status, render_nginx
from .runtime import self_install
from .service import service_control, service_install, service_remove, service_status
from .setup import MODES, SetupOptions, run_setup

__all__ = [
    "MODES",
    "SetupOptions",
    "clear_domain",
    "domain_info",
    "nginx_install",
    "nginx_remove",
    "nginx_status",
    "render_nginx",
    "route",
    "run_setup",
    "service_control",
    "service_install",
    "service_remove",
    "service_status",
    "self_install",
    "set_domain",
]
