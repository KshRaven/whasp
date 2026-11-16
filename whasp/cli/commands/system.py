"""Panel settings and information: config, logs, notes."""

from __future__ import annotations

import json
import sys
import time

from ...core import audit, config
from ..output import c

__all__ = ["cmd_config", "cmd_logs", "cmd_notes"]


def cmd_config(a):
    shown = config.public()
    if a.action == "set":
        protected = ("admin", "mfa")  # changed with `whasp passwd`, `whasp mfa` or the Settings page
        if a.key in protected or a.key not in config.DEFAULTS:
            sys.exit(f"unknown or protected key. Valid: {', '.join(k for k in config.DEFAULTS if k not in protected)}")
        try:
            value = json.loads(a.value)
        except ValueError:
            value = a.value
        try:
            config.cfg[a.key] = config.validate_setting(a.key, value)
        except ValueError as e:
            sys.exit(c("31", "error: ") + str(e))
        config.save()
        print(
            f"{a.key} updated. A running panel picks it up within a few seconds (restart it for host/port/tls changes)."
        )
    else:
        print(json.dumps(shown, indent=2))


def cmd_logs(a):
    for r in reversed(audit.tail(a.n)):
        print(time.strftime("%F %T", time.localtime(r.pop("ts"))), r.pop("event"), json.dumps(r))


def cmd_notes(a):
    from ...system import notify

    f = notify.feed(a.n, unread=not a.all)
    if not f["items"]:
        return print(c("32", "Nothing needs your attention."))
    for i in f["items"]:
        col = {"critical": "31", "warning": "33", "ok": "32"}.get(i["sev"], "0")
        print(
            c(col, f"{time.strftime('%d %b %H:%M', time.localtime(i['ts']))}  {i['sev']:<8} [{i['cat']}] {i['title']}")
        )
    if a.read:
        notify.mark_read()
