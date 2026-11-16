"""Operating-system layer. Everything that differs between Linux and Windows lives here, so the rest of
Whasp asks questions ("am I an administrator?", "where is nginx?") instead of checking os.name everywhere.
Standard library only. Supported: Linux and Windows (10/11, Server 2016+). Other systems fall back to the Linux paths."""

from __future__ import annotations

import ctypes
import glob
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

__all__ = [
    "EXAMPLE_ROOT",
    "IS_LINUX",
    "IS_ROOT",
    "IS_WIN",
    "NO_WINDOW",
    "OS_NAME",
    "RESERVED",
    "SHELL_CMD",
    "default_home",
    "defaults",
    "has_systemd",
    "is_admin",
    "local_ips",
    "perms_private",
    "pick",
    "pkg_manager",
    "secure",
    "which",
]

IS_WIN = os.name == "nt"
IS_LINUX = sys.platform.startswith("linux")
OS_NAME = "windows" if IS_WIN else "linux" if IS_LINUX else sys.platform
NO_WINDOW = 0x08000000 if IS_WIN else 0  # CREATE_NO_WINDOW: no console flashing when run as a service/task
SHELL_CMD = ["cmd.exe", "/c"] if IS_WIN else ["/bin/sh", "-c"]
RESERVED = re.compile(r"^(con|prn|aux|nul|com[0-9]|lpt[0-9])(\..*)?$", re.I)  # Windows device names


def pick(linux, windows):
    return windows if IS_WIN else linux


def is_admin():
    """root on Linux, an elevated Administrator on Windows."""
    if IS_WIN:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return os.geteuid() == 0


IS_ROOT = is_admin()
EXAMPLE_ROOT = str(Path.home() / "www") if IS_WIN and not IS_ROOT else "C:\\www" if IS_WIN else "/var/www"


def default_home():
    env = os.environ.get("WHASP_HOME")
    if env:
        return Path(env)
    if IS_WIN:
        pd = os.environ.get("ProgramData") or (os.environ.get("SystemDrive", "C:") + "\\ProgramData")
        return Path(pd) / "whasp" if IS_ROOT else Path.home() / ".whasp"
    return Path("/etc/whasp") if IS_ROOT else Path.home() / ".whasp"


def _drives():
    """Windows: every existing drive letter, so the whole system can be browsed."""
    found = [f"{c}:\\" for c in "CDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{c}:\\")]
    return found or [os.environ.get("SystemDrive", "C:") + "\\"]


def file_places(start=""):
    """Quick-access folders for the file manager (only the ones that exist)."""
    home = str(Path.home())
    if IS_WIN:
        pd, pf = os.environ.get("ProgramData", ""), os.environ.get("ProgramFiles", "")
        sd = os.environ.get("SystemDrive", "C:") + "\\"
        cand = [
            ("Start folder", start),
            ("Home", home),
            ("Program data", pd),
            ("Program files", pf),
            ("System drive", sd),
        ]
    else:
        cand = [
            ("Start folder", start),
            ("Home", home),
            ("Root", "/"),
            ("opt", "/opt"),
            ("etc", "/etc"),
            ("var/www", "/var/www"),
            ("var/log", "/var/log"),
            ("srv", "/srv"),
            ("usr/local", "/usr/local"),
            ("tmp", "/tmp"),
        ]
    seen, out = set(), []
    for name, path in cand:
        if path and os.path.isdir(path) and path not in seen:
            seen.add(path)
            out.append({"name": name, "path": path})
    return out


def defaults(home):
    """OS specific config defaults (merged into config.DEFAULTS)."""
    if IS_WIN:
        sd = os.environ.get("SystemDrive", "C:") + "\\"
        web_root = sd + "www" if IS_ROOT else str(Path.home() / "www")
        return {
            "services": ["W3SVC", "nginx", "sshd"],
            "file_roots": _drives() if IS_ROOT else [web_root, str(Path.home())],
            "file_start": web_root,  # where the file manager opens
            "web_roots": [web_root],
            "log_files": [sd + "nginx\\logs\\access.log", sd + "nginx\\logs\\error.log"],
            "backup_dir": str(home / "backups"),
            "bin_dirs": [sd + "nginx", sd + "Program Files\\nginx"],  # extra places to look for tools not on PATH
            "cron_user": "SYSTEM",
        }
    web_root = "/var/www" if IS_ROOT else str(Path.home() / "www")
    return {
        "services": ["nginx", "ssh"],
        "file_roots": ["/"] if IS_ROOT else [web_root, str(Path.home())],  # root browses the whole system
        "file_start": web_root,  # where the file manager opens
        "web_roots": [web_root],
        "log_files": [
            "/var/log/syslog",
            "/var/log/auth.log",
            "/var/log/nginx/access.log",
            "/var/log/nginx/error.log",
            "/var/log/messages",
        ],
        "backup_dir": "/var/backups/whasp" if IS_ROOT else str(home / "backups"),
        "bin_dirs": [],
        "cron_user": "root",
    }


_WIN_BIN_GLOBS = [
    "{pf}\\PostgreSQL\\*\\bin",
    "{pf}\\MySQL\\MySQL Server *\\bin",
    "{pf}\\MariaDB *\\bin",
    "{pf}\\Docker\\Docker\\resources\\bin",
    "{pf}\\Certbot\\bin",
]


def which(name, extra=()):
    """Like shutil.which, but also searches config `bin_dirs` and (Windows) the usual install folders,
    because services on Windows rarely have database/nginx folders on PATH."""
    hit = shutil.which(name)
    if hit:
        return hit
    try:
        from . import config

        dirs = list(config.cfg.get("bin_dirs") or [])
    except Exception:
        dirs = []
    dirs += list(extra)
    if IS_WIN:
        for base in {os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")} - {None}:
            for pat in _WIN_BIN_GLOBS:
                dirs += sorted(glob.glob(pat.format(pf=base)), reverse=True)
    return shutil.which(name, path=os.pathsep.join(dirs)) if dirs else None


def secure(path, directory=True):
    """Make a file/folder private to the operator. POSIX: chmod 700/600. Windows: replace the ACL with
    SYSTEM + Administrators + the current user (S-1-5-18 and S-1-5-32-544 are language independent)."""
    try:
        if IS_WIN:
            flag = "(OI)(CI)F" if directory else "F"
            grants = [f"*S-1-5-18:{flag}", f"*S-1-5-32-544:{flag}"]
            user, dom = os.environ.get("USERNAME", ""), os.environ.get("USERDOMAIN", "")
            if user and not user.endswith("$"):  # machine accounts (SYSTEM) are covered above
                grants.append(f"{dom + chr(92) if dom else ''}{user}:{flag}")
            subprocess.run(
                ["icacls", str(path), "/inheritance:r", "/grant:r", *grants],
                capture_output=True,
                timeout=30,
                creationflags=NO_WINDOW,
                stdin=subprocess.DEVNULL,
            )
        else:
            os.chmod(path, 0o700 if directory else 0o600)
    except (OSError, subprocess.SubprocessError):
        pass


def perms_private(path):
    """True/False on POSIX. None on Windows, where permissions are ACLs and not mode bits."""
    if IS_WIN:
        return None
    return (os.stat(path).st_mode & 0o077) == 0


def pkg_manager():
    """Name of the system package manager the panel can drive, or None.
    Linux: apt, dnf, yum, zypper, pacman, apk.  Windows: winget or choco."""
    if IS_WIN:
        return "winget" if which("winget") else "choco" if which("choco") else None
    for exe, name in (
        ("apt-get", "apt"),
        ("dnf", "dnf"),
        ("yum", "dnf"),
        ("zypper", "zypper"),
        ("pacman", "pacman"),
        ("apk", "apk"),
    ):
        if shutil.which(exe):
            return name
    return None


def has_systemd():
    return IS_LINUX and os.path.isdir("/run/systemd/system")


def local_ips():
    """Non-loopback IPv4 addresses of this machine (no network traffic: a UDP socket is only 'connected')."""
    import socket

    ips = []
    for target in ("192.0.2.1", "10.255.255.255"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((target, 9))
                ip = s.getsockname()[0]
                if ip not in ips and not ip.startswith("127."):
                    ips.append(ip)
        except OSError:
            pass
    try:
        for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = i[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except OSError:
        pass
    return ips
