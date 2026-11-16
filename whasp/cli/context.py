"""Shared start-up helpers for the commands: home folder, first admin, sign-in banner."""

from __future__ import annotations

import sys
from pathlib import Path

from ..core import config, plat
from .output import c

__all__ = ["START_HINT", "ensure_admin", "prepare_home", "show_login"]


START_HINT = (
    "schtasks /run /tn WhaspPanel"
    if plat.IS_WIN
    else "systemctl start whasp"
    if plat.IS_ROOT
    else "systemctl --user start whasp"
)


def prepare_home():
    try:
        for d in (config.HOME, config.HOME / "extensions", config.LOGDIR):
            d.mkdir(parents=True, exist_ok=True)
            plat.secure(d)  # chmod 700 on Linux, restricted ACL on Windows
        for d in (config.cfg.get("file_start"), *config.cfg.get("web_roots", [])[:1]):  # default file manager folder
            if d:
                Path(d).mkdir(parents=True, exist_ok=True)
    except PermissionError:
        sys.exit(
            f"Cannot write to {config.HOME} as this user. Check the directory ownership and permissions, "
            "or set WHASP_HOME to a writable private directory."
        )


def show_login(user, pw=None):
    from ..server.app import urls

    print(c("1", "\nSign in to the panel:"))
    for u in urls(config.cfg["host"], int(config.cfg["port"])):
        print(f"  {u}")
    print(f"  username: {user}")
    if pw:
        print(f"  password: {pw}   (shown once; change it with: whasp passwd)")


def ensure_admin():
    """First run straight after `pip install .`: create the config folder and the admin account, show the sign-in once."""
    if config.has_admin():
        return False
    prepare_home()
    pw = config.new_password()
    config.set_admin("admin", pw)
    config.save()
    print(c("1", "First run: the admin account was created."))
    show_login("admin", pw)
    print()
    return True
