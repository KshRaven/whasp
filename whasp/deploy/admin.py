"""Create the operator login during setup: arguments, WHASP_ADMIN_* variables, or an interactive prompt."""

from __future__ import annotations

import getpass
import os
import sys

from ..core import config
from ..core.errors import PanelError

__all__ = ["ensure_admin"]


def _prompt(user: str, password: str) -> tuple[str, str]:
    if not user:
        user = input("Admin username [admin]: ").strip() or "admin"
    if not password:
        for _ in range(3):
            first = getpass.getpass(f"Admin password (min {config.MIN_PASSWORD} chars, Enter = generate one): ")
            if not first:
                break
            if len(first) < config.MIN_PASSWORD:
                print(f"too short - at least {config.MIN_PASSWORD} characters")
                continue
            if getpass.getpass("Repeat: ") != first:
                print("passwords differ")
                continue
            password = first
            break
        else:
            raise PanelError("no valid password entered (nothing was changed; run the command again)")
    return user.strip(), password


def ensure_admin(user: str = "", password: str = "", prompt: bool = True) -> dict:
    """Make sure an admin login exists. Returns {"user", "password", "created"}; password is only filled in when it
    was generated here, so the caller can show it once. An existing login is kept unless a password was given."""
    user = user or os.environ.get("WHASP_ADMIN_USER", "")
    password = password or os.environ.get("WHASP_ADMIN_PASSWORD", "")
    exists = config.has_admin()
    if exists and not password:
        return {"user": config.cfg["admin"]["username"], "password": "", "created": False}
    if prompt and sys.stdin.isatty() and not (user and password):
        user, password = _prompt(user, password)
    generated = ""
    if not password:
        generated = password = config.new_password()
    try:
        config.set_admin(user or (config.cfg["admin"]["username"] if exists else "admin"), password)
    except ValueError as e:
        raise PanelError(str(e)) from e
    config.save()
    return {"user": config.cfg["admin"]["username"], "password": generated, "created": not exists}
