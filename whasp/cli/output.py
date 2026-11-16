"""Terminal output helpers: colours, bars, tables."""

from __future__ import annotations

import json
import sys

from ..core import plat
from ..extensions import Raw

__all__ = ["TTY", "bar", "c", "enable_ansi", "show", "size", "table"]


TTY = sys.stdout.isatty()


def enable_ansi():
    """Windows: UTF-8 output (bars use block characters) and ANSI colours on the console."""
    if not plat.IS_WIN:
        return
    for st in (sys.stdout, sys.stderr):
        if hasattr(st, "reconfigure"):
            st.reconfigure(encoding="utf-8", errors="replace")
    try:
        import ctypes

        k = ctypes.windll.kernel32
        h, m = k.GetStdHandle(-11), ctypes.c_ulong()
        if k.GetConsoleMode(h, ctypes.byref(m)):
            k.SetConsoleMode(h, m.value | 4)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass


def c(code, s):
    return f"\033[{code}m{s}\033[0m" if TTY else str(s)


def bar(v, width=24):
    n = int(width * min(max(v, 0), 100) / 100)
    col = "32" if v < 70 else "33" if v < 90 else "31"
    return c(col, "█" * n) + c("2", "░" * (width - n))


def size(n):
    n = float(n)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:.1f} {u}" if u != "B" else f"{int(n)} B"
        n /= 1024


def table(rows):
    if not rows:
        return print(c("2", "(nothing here)"))
    keys = list(rows[0])
    cell = lambda v: str(v)[:60]
    widths = [max(len(k), *(len(cell(r.get(k, ""))) for r in rows)) for k in keys]
    print(c("1;36", "  ".join(k.upper().ljust(w) for k, w in zip(keys, widths))))
    for r in rows:
        print("  ".join(cell(r.get(k, "")).ljust(w) for k, w in zip(keys, widths)))


def show(res):
    if isinstance(res, Raw):
        print(f"(binary, {len(res.data)} bytes: {res.filename})")
    elif isinstance(res, list) and res and isinstance(res[0], dict):
        table(res)
    elif isinstance(res, dict) and "text" in res:
        print(res["text"])
    else:
        print(json.dumps(res, indent=2))
