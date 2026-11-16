"""Example user extension. Copy to <config dir>/extensions/hello.py
(file must be owned by the panel user and not group/world-writable), then restart the panel.
"""

from __future__ import annotations

import time

from whasp.core.shell import run
from whasp.extensions import Extension

EXT = Extension("hello", "Hello", "👋", order=200, description="Example extension")


@EXT.route("uptime")  # GET /api/ext/hello/uptime
def uptime(params):
    return {"text": run(["uptime", "-p"])[1]}


@EXT.route("note", write=True)  # POST only, recorded in the audit log
def note(params):
    return {"text": f"saved '{params.get('msg', '')}' at {time.strftime('%T')}"}


EXT.sections = [
    {"type": "text", "title": "Uptime", "source": "uptime"},
    {
        "type": "form",
        "title": "Leave a note",
        "route": "note",
        "submit": "Save note",
        "fields": [{"name": "msg", "label": "Message", "required": True}],
    },
]
