"""Extensions: ext, call, svc, services."""

from __future__ import annotations

import sys

from ...core import audit
from ...core.errors import PanelError
from ...extensions import load_extensions, registry
from ..output import c, show, table

__all__ = ["cmd_call", "cmd_ext", "cmd_services", "cmd_svc"]


def cmd_ext(a):
    load_extensions()
    rows = [
        {
            "name": e.name,
            "available": "yes" if e.available else "missing: " + ",".join(e.missing),
            "routes": ",".join(e.routes),
            "about": e.description,
        }
        for e in registry.values()
    ]
    table(sorted(rows, key=lambda r: r["name"]))


def cmd_call(a):
    """Run any extension route locally: whasp call docker containers"""
    load_extensions()
    ext = registry.get(a.ext)
    if not ext:
        sys.exit(f"unknown extension '{a.ext}'. Try: whasp ext")
    if a.route not in ext.routes:
        sys.exit(f"unknown route. Available: {', '.join(ext.routes)}")
    params = dict(kv.split("=", 1) for kv in a.params if "=" in kv)
    fn, write = ext.routes[a.route]
    try:
        if write:
            audit.log("action", ip="cli", ext=a.ext, route=a.route, params=audit.redact(params))
        show(fn(params))
    except PanelError as e:
        sys.exit(c("31", "error: ") + e.message)


def cmd_svc(a):
    a.ext, a.route, a.params = "services", "action", [f"name={a.name}", f"op={a.op}"]
    cmd_call(a)


def cmd_services(a):
    a.ext, a.route, a.params = "services", "list", []
    cmd_call(a)
