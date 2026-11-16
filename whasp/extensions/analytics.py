"""Website analytics: visitors, pages, errors and bots from web server access logs.

Reads nginx / Apache "combined" format logs (no tracking script, nothing leaves the server). Only the newest
`MAX_BYTES` of a log are read, so even very large logs answer quickly.
"""

from __future__ import annotations

import glob
import os
import re
import time
from collections import Counter
from datetime import datetime

from ..core import plat
from ..core.errors import PanelError
from . import Extension

__all__ = ["EXT", "analyze", "parse_line"]

WIN = plat.IS_WIN
EXT = Extension(
    "analytics",
    "Analytics",
    "📈",
    order=72,
    group="Websites",
    description="Visitors, popular pages, status codes, referrers and bots from your access logs",
)
MAX_BYTES = 20 * 1024 * 1024
LINE = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[(?P<ts>[^\]]+)\] "(?P<method>[A-Z]+) (?P<path>\S*)[^"]*" (?P<status>\d{3}) (?P<bytes>\d+|-)'
    r'(?: "(?P<ref>[^"]*)" "(?P<ua>[^"]*)")?'
)
BOT = re.compile(r"bot|crawl|spider|slurp|curl|wget|python-requests|scrapy|headless|monitor|uptime", re.I)
ASSET = re.compile(r"\.(css|js|map|png|jpe?g|gif|svg|ico|webp|woff2?|ttf|eot|mp4|webm)(\?|$)", re.I)


def _globs():
    if WIN:
        nd = plat.which("nginx")
        return [os.path.join(os.path.dirname(nd), "logs", "*access*.log")] if nd else []
    return [
        "/var/log/nginx/*access*.log",
        "/var/log/apache2/*access*.log",
        "/var/log/httpd/*access_log",
        "/www/wwwlogs/*.log",
    ]


def _files():
    out = []
    for g in _globs():
        out += [f for f in glob.glob(g) if os.path.isfile(f) and not f.endswith(".gz")]
    return sorted(set(out))


def parse_line(line):
    m = LINE.match(line)
    if not m:
        return None
    d = m.groupdict()
    try:
        d["when"] = datetime.strptime(d["ts"].split()[0], "%d/%b/%Y:%H:%M:%S")
    except ValueError:
        return None
    d["bytes"] = int(d["bytes"]) if d["bytes"] and d["bytes"] != "-" else 0
    d["status"] = int(d["status"])
    d["ua"] = d.get("ua") or ""
    d["ref"] = d.get("ref") or ""
    return d


def analyze(lines, top=10):
    """Summarise parsed log lines. Pure function: pass any iterable of log lines."""
    total = bots = nbytes = 0
    ips, pages, refs, status, hours, days = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
    ips_human, errors = set(), Counter()
    for line in lines:
        r = parse_line(line)
        if not r:
            continue
        total += 1
        nbytes += r["bytes"]
        status[f"{r['status'] // 100}xx"] += 1
        is_bot = bool(BOT.search(r["ua"]))
        bots += is_bot
        days[r["when"].strftime("%Y-%m-%d")] += 1
        if is_bot:
            continue
        ips[r["ip"]] += 1
        ips_human.add(r["ip"])
        hours[r["when"].hour] += 1
        if not ASSET.search(r["path"]):
            pages[r["path"].split("?")[0]] += 1
            if r["status"] >= 400:
                errors[(r["path"].split("?")[0], r["status"])] += 1
        if r["ref"] and r["ref"] != "-":
            host = re.sub(r"^https?://([^/]+).*", r"\1", r["ref"])
            refs[host] += 1
    return {
        "requests": total,
        "visitors": len(ips_human),
        "bots": bots,
        "bytes": nbytes,
        "status": dict(status),
        "pages": [{"path": k, "hits": v} for k, v in pages.most_common(top)],
        "ips": [{"ip": k, "hits": v} for k, v in ips.most_common(top)],
        "referrers": [{"site": k, "hits": v} for k, v in refs.most_common(top)],
        "errors": [{"path": k[0], "status": k[1], "hits": v} for k, v in errors.most_common(top)],
        "hours": [hours.get(h, 0) for h in range(24)],
        "days": [{"day": k, "hits": days[k]} for k in sorted(days)[-14:]],
    }


def _read(path):
    if path not in _files():
        raise PanelError("unknown log file", 404)
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        f.seek(max(0, size - MAX_BYTES))
        data = f.read().decode("utf-8", "replace")
    return data.splitlines()[1:] if size > MAX_BYTES else data.splitlines()


def _log(p):
    files = _files()
    want = str(p.get("log", ""))
    if want:
        return want
    if not files:
        raise PanelError("no access logs found yet (they appear once nginx or Apache has served a request)", 404)
    return files[0]


@EXT.route("logs")
def logs(p):
    return [{"log": f, "size": os.path.getsize(f), "mtime": int(os.path.getmtime(f))} for f in _files()]


@EXT.route("summary")
def summary(p):
    r = analyze(_read(_log(p)))
    return [
        {"label": "Requests", "value": r["requests"]},
        {"label": "Visitors (IPs)", "value": r["visitors"]},
        {"label": "Bot requests", "value": r["bots"]},
        {"label": "Traffic", "value": f"{r['bytes'] / 1048576:.1f} MB"},
        {"label": "Errors (4xx/5xx)", "value": r["status"].get("4xx", 0) + r["status"].get("5xx", 0), "state": "warn"},
    ]


def _part(key):
    @EXT.route(key)
    def fn(p, _k=key):
        return analyze(_read(_log(p)), top=int(p.get("top", 15) or 15))[_k]

    fn.__name__ = key
    return fn


for _k in ("pages", "ips", "referrers", "errors", "days"):
    _part(_k)


@EXT.route("report")
def report(p):
    r = analyze(_read(_log(p)))
    peak = max(range(24), key=lambda h: r["hours"][h]) if r["requests"] else 0
    lines = [
        f"Log: {_log(p)}   (generated {time.strftime('%Y-%m-%d %H:%M')})",
        f"Requests {r['requests']}  |  visitors {r['visitors']}  |  bots {r['bots']}  |  {r['bytes'] / 1048576:.1f} MB",
        "Status: " + "  ".join(f"{k}={v}" for k, v in sorted(r["status"].items())),
        f"Busiest hour: {peak:02d}:00",
        "",
        "Top pages:",
    ]
    lines += [f"  {x['hits']:>7}  {x['path']}" for x in r["pages"]]
    lines += ["", "Top referrers:"] + [f"  {x['hits']:>7}  {x['site']}" for x in r["referrers"]]
    return {"text": "\n".join(lines)}


EXT.sections = [
    {
        "type": "form",
        "title": "Choose a log (leave empty for the first one)",
        "route": "report",
        "method": "GET",
        "submit": "Show report",
        "fields": [{"name": "log", "label": "Log file path", "placeholder": "/var/log/nginx/access.log"}],
    },
    {"type": "stats", "source": "summary", "refresh": 60},
    {"type": "table", "title": "Top pages", "source": "pages", "columns": [["Page", "path", "mono"], ["Hits", "hits", "num"]]},
    {"type": "table", "title": "Top visitors", "source": "ips", "columns": [["Address", "ip", "mono"], ["Hits", "hits", "num"]]},
    {"type": "table", "title": "Referrers", "source": "referrers", "columns": [["Site", "site"], ["Hits", "hits", "num"]]},
    {
        "type": "table",
        "title": "Errors",
        "source": "errors",
        "columns": [["Page", "path", "mono"], ["Status", "status"], ["Hits", "hits", "num"]],
    },
    {"type": "table", "title": "Requests per day", "source": "days", "columns": [["Day", "day"], ["Requests", "hits", "num"]]},
    {"type": "table", "title": "Access logs found", "source": "logs", "columns": [["File", "log", "mono"], ["Size", "size", "bytes"], ["Updated", "mtime", "time"]]},
]
