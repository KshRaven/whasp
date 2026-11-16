"""Account commands: init, passwd, user, mfa, privacy."""

from __future__ import annotations

import json
import sys

from ...auth import mfa
from ...core import audit, config, plat
from ...core.errors import PanelError
from ..context import START_HINT, prepare_home, show_login
from ..output import c

__all__ = ["cmd_init", "cmd_mfa", "cmd_passwd", "cmd_privacy", "cmd_user"]


def cmd_init(a):
    """Create the config folder and the admin account (username and password, no tokens)."""
    prepare_home()
    if config.has_admin() and not a.reset:
        print(f"Already initialised ({config.CONFIG}). Use --reset to set a new username/password.")
        return
    user = a.user or (config.cfg["admin"]["username"] if config.has_admin() else "admin")
    pw = a.password or config.new_password()
    try:
        config.set_admin(user, pw)
    except ValueError as e:
        sys.exit(str(e))
    config.save()
    print(f"Config: {config.CONFIG}")
    print(f"Files open at: {config.cfg.get('file_start')}")
    show_login(user, None if a.password else pw)
    if not plat.IS_WIN and not plat.IS_ROOT:
        print("This is a per-user setup. For a system-wide install that `sudo whasp` can find:  whasp self-install")
    print(f"\nBring the website up with:  whasp start     (foreground: whasp web;  as a service: {START_HINT})")


def cmd_passwd(a):
    import getpass

    if not config.has_admin():
        sys.exit("No admin account yet. Run: whasp init")
    pw = a.password
    if not pw:
        pw = getpass.getpass("New password: ")
        if pw != getpass.getpass("Repeat it: "):
            sys.exit("passwords do not match")
    try:
        config.set_admin(a.user, pw)
    except ValueError as e:
        sys.exit(str(e))
    config.save()
    audit.log("account_changed", ip="cli", user=config.cfg["admin"]["username"])
    print("Password updated for", config.cfg["admin"]["username"], "(open sessions end when the panel restarts).")


def cmd_user(a):
    print(config.cfg["admin"]["username"] or "(not set: run whasp init)")


def cmd_mfa(a):
    if a.action == "reset":
        mfa.reset_all()
        print("All second factors removed. Sign-in needs only the password again. Re-enable in Settings.")
    elif a.action == "test-email":
        to = a.to or config.cfg["mfa"].get("email")
        if not to:
            sys.exit("give an address: whasp mfa test-email you@example.com")
        try:
            mfa.send_mail(to, "whasp test", "SMTP works. You can enable e-mail sign-in codes in Settings.")
        except PanelError as e:
            sys.exit(c("31", "error: ") + e.message)
        print("sent to", to)
    else:
        st = mfa.status()
        print(
            f"authenticator app: {'on' if st['totp'] else 'off'}\ne-mail codes:      {'on (' + st['email_address'] + ')' if st['email'] else 'off'}\nSMTP configured:   {'yes' if st['smtp_configured'] else 'no'}"
        )


def cmd_privacy(a):
    if a.action == "export":
        print(json.dumps({"config": config.public(), "audit_events": audit.tail(5000)}, indent=2))
    else:
        if (
            not a.yes
            and input("Delete the audit log, authenticator secret and MFA e-mail? Type 'delete': ") != "delete"
        ):
            sys.exit("cancelled")
        n = audit.erase()
        mfa.reset_all()
        audit.log("privacy_delete", files=n)
        print(f"Deleted {n} audit file(s) and cleared MFA data. Restart/reload the panel to drop open sessions.")
