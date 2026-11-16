from __future__ import annotations

import base64
import functools
import os
import re
import shutil
import stat
import sys

from ..core import config, plat
from ..core.errors import PanelError
from ..core.shell import safe_path
from . import Extension, Raw
from .filetypes import inspect_text

__all__ = ["EXT"]

EXT = Extension(
    "files",
    "Files",
    "folder",
    order=30,
    ui="files",
    description="Browse the whole server (as root/Administrator) or your own folders, edit configuration files with syntax checks, upload, move and copy.",
)
BAD_WIN_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
MAX_EDIT, MAX_UPLOAD, MAX_DOWNLOAD = 2 << 20, 8 << 20, 100 << 20


# System folders that can be browsed and edited but never deleted, renamed or moved from the panel.
PROTECTED = {
    "/", "/bin", "/boot", "/dev", "/etc", "/home", "/lib", "/lib32", "/lib64", "/opt", "/proc", "/root", "/run",
    "/sbin", "/srv", "/sys", "/usr", "/var", "/usr/bin", "/usr/lib", "/usr/local", "/usr/sbin", "/var/lib", "/var/www",
}  # fmt: skip


def _roots():
    return config.cfg["file_roots"]


def _start():
    """Where the file manager opens: file_start when it exists inside a root, else the first root."""
    want = config.cfg.get("file_start") or ""
    try:
        if want and os.path.isdir(want):
            return safe_path(want, _roots())
    except PanelError:
        pass
    return _roots()[0]


def _dir(path):
    return safe_path(path or _start(), _roots())


def _protected(path):
    real = os.path.realpath(path)
    if os.path.dirname(real) == real:  # a drive or the filesystem root
        return True
    if plat.IS_WIN:
        sd = os.environ.get("SystemDrive", "C:") + "\\"
        return real.lower() in {
            os.path.join(sd, d).lower() for d in ("windows", "program files", "users", "programdata")
        }
    return real.rstrip("/") in PROTECTED


def _oserr(fn):
    """Turn OS errors (locked file, permission, missing path) into a clean API error instead of a 500."""

    @functools.wraps(fn)
    def wrapper(p):
        try:
            return fn(p)
        except PermissionError as e:
            raise PanelError(f"permission denied or file in use: {e.filename}", 403)
        except OSError as e:
            raise PanelError(f"{e.strerror}: {e.filename}", 400)

    return wrapper


def _name(n):
    if not isinstance(n, str) or n in ("", ".", "..") or "/" in n or "\0" in n:
        raise PanelError("invalid name")
    if plat.IS_WIN and (BAD_WIN_NAME.search(n) or n.endswith((" ", ".")) or plat.RESERVED.match(n)):
        raise PanelError("invalid name for a Windows file system")
    return n


def _is_link(path):
    """Symlink, or on Windows any reparse point (junctions are not reported by islink)."""
    if os.path.islink(path):
        return True
    if plat.IS_WIN:
        try:
            return bool(os.lstat(path).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
        except OSError:
            return False
    return False


def _rmtree(path):
    def fix(func, p, *_):  # Windows refuses to delete read-only files
        os.chmod(p, stat.S_IWRITE)
        func(p)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=fix)
    else:
        shutil.rmtree(path, onerror=fix)


def _entry(path):
    """Resolve the parent directory only, so symlinks are acted on, not followed."""
    d, n = os.path.split(str(path).rstrip("/\\" if plat.IS_WIN else "/"))
    return os.path.join(safe_path(d or os.sep, _roots()), _name(n))


def _is_root(p):
    return any(os.path.realpath(r) == os.path.realpath(p) for r in _roots())


@EXT.route("list")
@_oserr
def list_(p):
    path = _dir(p.get("path"))
    if not os.path.isdir(path):
        raise PanelError(
            "this is a file, not a folder"
            if os.path.isfile(path)
            else "this folder does not exist (it may have been moved or deleted)",
            404,
        )
    rows = []
    with os.scandir(path) as it:
        for e in it:
            try:
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            kind = "link" if _is_link(e.path) else "dir" if e.is_dir() else "file"
            rows.append({"name": e.name, "type": kind, "size": st.st_size, "mtime": int(st.st_mtime)})
    rows.sort(key=lambda r: (r["type"] != "dir", r["name"].lower()))
    return {
        "path": path,
        "parent": None if _is_root(path) else os.path.dirname(path),
        "entries": rows,
        "sep": os.sep,
        "win": plat.IS_WIN,
    }


@EXT.route("roots")
def roots(p):
    out = []
    for r in _roots():
        if os.path.isdir(r):
            out.append(
                {
                    "path": os.path.realpath(r),
                    "name": os.path.basename(os.path.realpath(r).rstrip("/\\")) or os.path.realpath(r),
                }
            )
    return out


@EXT.route("places")
def places(p):
    """Where to open and the quick-access folders (only those inside the allowed roots)."""
    out = []
    for item in plat.file_places(_start()):
        try:
            out.append({"name": item["name"], "path": safe_path(item["path"], _roots())})
        except PanelError:
            continue
    return {
        "start": _start(),
        "places": out,
        "system": any(os.path.dirname(os.path.realpath(r)) == os.path.realpath(r) for r in _roots()),
    }


@EXT.route("inspect")
@_oserr
def inspect(p):
    """Syntax-check the text being edited (nothing is run). live=1 also asks the real tool, e.g. `nginx -t`."""
    path = _dir(p.get("path"))
    text = str(p.get("content", ""))
    if len(text.encode("utf-8", "ignore")) > MAX_EDIT:
        raise PanelError("content too large")
    return inspect_text(path, text, p.get("live") in (True, "true", "1", 1))


@EXT.route("read")
@_oserr
def read(p):
    path = _dir(p.get("path"))
    if not os.path.isfile(path):
        raise PanelError("not a file")
    if os.path.getsize(path) > MAX_EDIT:
        raise PanelError("file is larger than the 2 MB edit limit; download it instead")
    with open(path, "rb") as f:
        data = f.read()
    if b"\0" in data:
        raise PanelError("binary file; use download")
    return {"path": path, "content": data.decode("utf-8", "replace")}


@EXT.route("write", write=True)
@_oserr
def write(p):
    path = _dir(p.get("path"))
    data = str(p.get("content", "")).encode()
    if len(data) > MAX_EDIT:
        raise PanelError("content too large")
    if os.path.isdir(path):
        raise PanelError("path is a directory")
    backup = ""
    if p.get("backup") in (True, "true", "1", 1) and os.path.isfile(path):
        backup = path + ".bak"  # one backup next to the file: the version before this save
        shutil.copy2(path, backup)
    with open(path, "wb") as f:
        f.write(data)
    return {"ok": True, "backup": backup}


@EXT.route("mkdir", write=True)
@_oserr
def mkdir(p):
    os.mkdir(os.path.join(_dir(p.get("path")), _name(p.get("name"))))
    return {"ok": True}


@EXT.route("delete", write=True)
@_oserr
def delete(p):
    t = _entry(p.get("path"))
    if _is_root(t) or _protected(t):
        raise PanelError("cannot delete a root or system folder", 403)
    if _is_link(t):  # remove the link itself, never what it points at
        os.rmdir(t) if plat.IS_WIN and os.path.isdir(t) else os.remove(t)
    elif os.path.isdir(t):
        _rmtree(t)
    else:
        os.remove(t)
    return {"ok": True}


@EXT.route("rename", write=True)
@_oserr
def rename(p):
    src = _entry(p.get("path"))
    dst = os.path.join(os.path.dirname(src), _name(p.get("new_name")))
    if _is_root(src) or _protected(src) or os.path.lexists(dst):
        raise PanelError("cannot rename (root or system folder, or the target exists)")
    os.rename(src, dst)
    return {"ok": True}


@EXT.route("upload", write=True)
@_oserr
def upload(p):
    dest = os.path.join(_dir(p.get("path")), _name(p.get("name")))
    b64 = str(p.get("data", ""))
    if len(b64) * 3 // 4 > MAX_UPLOAD:
        raise PanelError("upload exceeds 8 MB")
    if os.path.isdir(dest):
        raise PanelError("a folder with that name exists")
    try:
        raw = base64.b64decode(b64, validate=True)
    except ValueError:
        raise PanelError("invalid upload data")
    with open(dest, "wb") as f:
        f.write(raw)
    return {"ok": True}


@EXT.route("download")
@_oserr
def download(p):
    path = _dir(p.get("path"))
    if not os.path.isfile(path):
        raise PanelError("not a file")
    if os.path.getsize(path) > MAX_DOWNLOAD:
        raise PanelError("file exceeds the 100 MB download limit; use scp/rsync")
    with open(path, "rb") as f:
        return Raw(f.read(), filename=os.path.basename(path))


def _paths(p):
    v = p.get("paths")
    if not isinstance(v, list) or not v or len(v) > 500:
        raise PanelError("nothing selected")
    return [_entry(x) for x in v]


def _unique(dest, name):
    stem, ext = os.path.splitext(name)
    cand, n = name, 1
    while os.path.lexists(os.path.join(dest, cand)):
        cand = f"{stem} copy{'' if n == 1 else ' ' + str(n)}{ext}"
        n += 1
    return cand


def _into_self(src, dest):
    a, b = os.path.normcase(os.path.realpath(src)), os.path.normcase(os.path.realpath(dest))
    return b == a or b.startswith(a.rstrip("/\\") + os.sep)


@EXT.route("move", write=True)
@_oserr
def move(p):
    dest = _dir(p.get("dest"))
    if not os.path.isdir(dest):
        raise PanelError("destination is not a folder")
    for src in _paths(p):
        if _is_root(src) or _protected(src):
            raise PanelError("cannot move a root or system folder", 403)
        name = os.path.basename(src)
        if os.path.isdir(src) and _into_self(src, dest):
            raise PanelError(f"cannot move {name} into itself")
        if os.path.dirname(src) == dest:
            continue
        target = os.path.join(dest, name)
        if os.path.lexists(target):
            raise PanelError(f"{name} already exists in the destination")
        shutil.move(src, target)
    return {"ok": True}


@EXT.route("copy", write=True)
@_oserr
def copy(p):
    dest = _dir(p.get("dest"))
    if not os.path.isdir(dest):
        raise PanelError("destination is not a folder")
    for src in _paths(p):
        name = _unique(dest, os.path.basename(src))
        target = os.path.join(dest, name)
        if os.path.isdir(src) and not _is_link(src):
            if _into_self(src, dest):
                raise PanelError(f"cannot copy {os.path.basename(src)} into itself")
            shutil.copytree(src, target, symlinks=True)
        else:
            shutil.copy2(src, target, follow_symlinks=False)
    return {"ok": True}


@EXT.route("delete_many", write=True)
@_oserr
def delete_many(p):
    for t in _paths(p):
        delete({"path": t})
    return {"ok": True}
