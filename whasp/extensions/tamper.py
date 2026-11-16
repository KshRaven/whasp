"""Tamper protection: detect, report and optionally lock changes to website files.

Records a SHA-256 baseline per protected folder. Scan lists files added, changed or removed since; Lock makes the
folder immutable (`chattr +i` on Linux, a deny-write ACL on Windows); Accept takes a new baseline (unlock before
deploying). A background scan runs every `tamper_interval` minutes (default 60) and raises one Security
notification per folder with changes.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path

from ..core import audit, config, plat
from ..core.errors import PanelError
from ..core.shell import run, safe_path
from ..system import notify
from . import Extension

__all__ = ["EXT", "scan_folder", "snapshot"]

WIN = plat.IS_WIN
EXT = Extension(
    "tamper",
    "Tamper protection",
    "🔏",
    order=53,
    group="Security",
    description="Baseline, scan and lock website folders so unexpected file changes are caught",
)
MAX_FILES = 50_000
SKIP_DIRS = {".git", "node_modules", "__pycache__", "cache", "tmp", "logs"}
_lock = threading.Lock()
_started = False


def _db():
    return config.HOME / "tamper.json"


def _load():
    try:
        return json.loads(_db().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(data):
    config.HOME.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = _db().with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.replace(tmp, _db())


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot(folder):
    """{relative path: [sha256, size]} for every regular file under folder (links are not followed)."""
    root, out = Path(folder), {}
    for dirpath, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in files:
            f = Path(dirpath) / n
            if f.is_symlink() or not f.is_file():
                continue
            if len(out) >= MAX_FILES:
                raise PanelError(f"more than {MAX_FILES} files: protect a smaller folder")
            try:
                out[f.relative_to(root).as_posix()] = [_sha(f), f.stat().st_size]
            except OSError:
                continue
    return out


def scan_folder(folder, base):
    now = snapshot(folder)
    added = sorted(set(now) - set(base))
    removed = sorted(set(base) - set(now))
    changed = sorted(k for k in set(now) & set(base) if now[k][0] != base[k][0])
    return {"added": added, "removed": removed, "changed": changed}


def _folder(p):
    path = safe_path(str(p.get("path", "")), config.cfg["file_roots"])
    if not os.path.isdir(path):
        raise PanelError("folder not found", 404)
    return str(Path(path))


def _lock_cmd(folder, on):
    if WIN:
        user = os.environ.get("USERNAME", "Everyone")
        return ["icacls", folder, "/deny" if on else "/remove:d", f"{user}:(OI)(CI)(WD,AD,DC)" if on else user, "/T", "/C"]
    return ["chattr", "-R", "+i" if on else "-i", folder]


@EXT.route("list")
def list_(p):
    rows = []
    for folder, info in sorted(_load().items()):
        rows.append(
            {
                "path": folder,
                "files": len(info.get("files", {})),
                "taken": info.get("taken", 0),
                "locked": bool(info.get("locked")),
                "changes": info.get("changes", 0),
            }
        )
    return rows


@EXT.route("stats")
def stats(p):
    rows = list_(p)
    return [
        {"label": "Protected folders", "value": len(rows)},
        {"label": "Locked", "value": sum(r["locked"] for r in rows)},
        {"label": "With changes", "value": sum(1 for r in rows if r["changes"]), "state": "warn"},
    ]


@EXT.route("protect", write=True)
def protect(p):
    folder = _folder(p)
    files = snapshot(folder)
    with _lock:
        data = _load()
        data[folder] = {"files": files, "taken": int(time.time()), "locked": data.get(folder, {}).get("locked", False), "changes": 0}
        _save(data)
    _ensure_checker()
    audit.log("tamper_protect", path=folder, files=len(files))
    return {"text": f"baseline taken for {len(files)} files in {folder}"}


@EXT.route("scan")
def scan(p):
    folder = _folder(p)
    info = _load().get(folder)
    if not info:
        raise PanelError("this folder is not protected yet", 404)
    r = scan_folder(folder, info["files"])
    n = len(r["added"]) + len(r["removed"]) + len(r["changed"])
    with _lock:
        data = _load()
        if folder in data:
            data[folder]["changes"] = n
            _save(data)
    if not n:
        return {"text": "no changes since the baseline"}
    lines = [f"{n} change(s) since {time.strftime('%Y-%m-%d %H:%M', time.localtime(info['taken']))}:"]
    for label in ("changed", "added", "removed"):
        lines += [f"  {label:8} {x}" for x in r[label][:200]]
        if len(r[label]) > 200:
            lines.append(f"  ... and {len(r[label]) - 200} more {label}")
    return {"text": "\n".join(lines)}


@EXT.route("accept", write=True)
def accept(p):
    return protect(p) | {"text": "changes accepted: new baseline taken"}


@EXT.route("lock", write=True)
def lock(p):
    folder = _folder(p)
    data = _load()
    if folder not in data:
        raise PanelError("protect the folder first", 404)
    on = str(p.get("off", "")) not in ("1", "true", "True")
    if not WIN and not plat.which("chattr"):
        raise PanelError("chattr is not available on this system (install e2fsprogs)")
    rc, out = run(_lock_cmd(folder, on), timeout=300)
    if rc:
        raise PanelError(("lock" if on else "unlock") + " failed: " + out[-300:] + " (needs root / Administrator)")
    with _lock:
        data = _load()
        data[folder]["locked"] = on
        _save(data)
    audit.log("tamper_lock", path=folder, locked=on)
    return {"text": ("locked " if on else "unlocked ") + folder}


@EXT.route("remove", write=True)
def remove(p):
    folder = str(p.get("path", ""))
    with _lock:
        data = _load()
        info = data.get(folder)
        if not info:
            raise PanelError("not protected", 404)
        if info.get("locked"):
            raise PanelError("unlock the folder before removing protection")
        del data[folder]
        _save(data)
    return {"ok": True}


def _check_all():
    for folder, info in _load().items():
        try:
            r = scan_folder(folder, info["files"])
        except (OSError, PanelError):
            continue
        n = len(r["added"]) + len(r["removed"]) + len(r["changed"])
        with _lock:
            data = _load()
            if folder in data:
                data[folder]["changes"] = n
                _save(data)
        if n:
            notify.add(
                "security",
                "warning",
                f"Files changed in {folder}",
                f"{len(r['changed'])} changed, {len(r['added'])} added, {len(r['removed'])} removed since the baseline.",
                key=f"tamper:{folder}",
            )
        else:
            notify.resolve(f"tamper:{folder}", f"No changes in {folder}")


def _loop():
    while True:
        time.sleep(max(5, int(config.cfg.get("tamper_interval", 60))) * 60)
        try:
            _check_all()
        except Exception:  # a background scan must never kill the thread
            pass


def _ensure_checker():
    global _started
    if not _started:
        _started = True
        threading.Thread(target=_loop, name="whasp-tamper", daemon=True).start()


if _load():
    _ensure_checker()

EXT.sections = [
    {"type": "stats", "source": "stats", "refresh": 30},
    {
        "type": "help",
        "title": "How it works",
        "text": "Protect a folder to record its files now. Scan shows what changed since. Lock makes it read-only for everyone "
        "(for finished sites). Unlock and Accept changes when you deploy.",
    },
    {
        "type": "table",
        "title": "Protected folders",
        "source": "list",
        "refresh": 30,
        "columns": [
            ["Folder", "path", "mono"],
            ["Files", "files", "num"],
            ["Baseline", "taken", "time"],
            ["Changes", "changes", "num"],
            ["Locked", "locked", "bool"],
        ],
        "actions": [
            {"label": "Scan", "route": "scan", "method": "GET", "params": {"path": "$path"}},
            {"label": "Accept changes", "route": "accept", "params": {"path": "$path"}, "confirm": "Take a new baseline?"},
            {"label": "Lock", "route": "lock", "params": {"path": "$path"}, "ifnot": "locked", "confirm": "Make this folder read-only?"},
            {"label": "Unlock", "route": "lock", "params": {"path": "$path", "off": "1"}, "if": "locked"},
            {
                "label": "Remove",
                "route": "remove",
                "params": {"path": "$path"},
                "confirm": "Stop protecting this folder?",
                "danger": True,
                "ifnot": "locked",
            },
        ],
    },
    {
        "type": "form",
        "title": "Protect a folder",
        "route": "protect",
        "submit": "Take baseline",
        "fields": [{"name": "path", "label": "Folder (inside file roots)", "required": True, "placeholder": os.path.join(plat.EXAMPLE_ROOT, "example.com")}],
    },
]
