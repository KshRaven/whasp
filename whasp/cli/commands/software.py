"""Software catalog: install, uninstall, catalog."""

from __future__ import annotations

import os
import sys

from ...core import audit, plat
from ...core.errors import PanelError
from ..output import c, table

__all__ = ["cmd_catalog", "cmd_install", "cmd_uninstall", "plan_args", "run_plan"]


def run_plan(title, steps, env):
    """Run an install/uninstall plan from catalog.py in the foreground with the output on screen."""
    import subprocess

    from ...core.shell import resolve_command

    print(c("1;36", title))
    full_env = {**os.environ, **env}
    for step in steps:
        optional = False
        if isinstance(step, dict):
            step, optional = step["cmd"], step.get("optional", False)
        if callable(step):
            out = step()
            if out:
                print(out)
            continue
        argv = resolve_command(list(step))
        print(c("2", "$ " + " ".join(argv)), flush=True)
        try:
            rc = subprocess.run(argv, env=full_env, creationflags=plat.NO_WINDOW).returncode
        except OSError as e:
            sys.exit(c("31", "error: ") + str(e))
        if rc and not optional:
            sys.exit(c("31", f"failed (exit code {rc})"))
    print(c("32", "done"))


def plan_args(a, uninstall):
    from ...software import catalog

    try:
        e = catalog.get(a.name)
        return (catalog.uninstall_plan if uninstall else catalog.install_plan)(e["id"])
    except PanelError as err:
        sys.exit(c("31", "error: ") + err.message)


def cmd_install(a):
    """whasp install nginx   (see `whasp catalog` for the list)"""
    audit.log("action", ip="cli", ext="services", route="install", params={"name": a.name})
    run_plan(*plan_args(a, False))


def cmd_uninstall(a):
    if not a.yes and input(f"Remove {a.name}? Its data is kept. Type 'yes': ") != "yes":
        sys.exit("cancelled")
    audit.log("action", ip="cli", ext="services", route="uninstall", params={"name": a.name})
    run_plan(*plan_args(a, True))


def cmd_catalog(a):
    from ...software import catalog

    rows = [
        {
            "id": r["id"],
            "state": "not installed" if not r["installed"] else r["state"],
            "category": r["category"],
            "what": r["summary"][:70],
        }
        for r in catalog.listing()
    ]
    table(rows)
    print(c("2", "\nInstall with: whasp install <id>      Remove with: whasp uninstall <id>"))
