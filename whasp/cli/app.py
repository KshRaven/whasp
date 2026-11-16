"""Entry point of the `whasp` command."""

from __future__ import annotations

import sys

from .context import ensure_admin
from .output import TTY, enable_ansi
from .parser import build_parser

__all__ = ["main"]


def main(argv=None):
    parser = build_parser()
    enable_ansi()
    args = parser.parse_args(argv)
    if not args.cmd:  # plain `whasp`: the terminal app (falls back to help where curses is missing)
        if ensure_admin() and TTY:
            input("Note the password above, then press Enter to open the terminal app... ")
        try:
            from ..tui import main as tui
        except ImportError:
            return parser.print_help()
        return tui()
    try:
        args.f(args)
    except KeyboardInterrupt:
        sys.exit(130)
