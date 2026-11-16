"""File type checks for the file manager editor, plus the hook extensions use to add their own.

The editor's Check button sends the text here; every handler whose pattern matches the file name returns a list
of problems. Nothing is executed (shell, JavaScript and PHP are only syntax-checked).

Add a type from an extension (<config dir>/extensions/*.py):

    from whasp.extensions.filetypes import file_handler

    @file_handler("caddy", names=["Caddyfile"], label="Caddyfile")
    def check_caddy(path, text, live=False):
        return [{"line": 3, "message": "unknown directive"}] if "bogus" in text else []
"""

from __future__ import annotations

import configparser
import fnmatch
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Callable
from xml.etree import ElementTree

from ..core import plat

__all__ = ["HANDLERS", "file_handler", "inspect_text", "problem"]

HANDLERS: dict[str, dict] = {}  # name -> {"label", "exts", "names", "globs", "fn"}; re-registering a name replaces it


def problem(message: str, line: int = 0, col: int = 0, level: str = "error") -> dict:
    return {"line": int(line or 0), "col": int(col or 0), "level": level, "message": str(message)}


def file_handler(name: str, exts=(), names=(), globs=(), label: str = "") -> Callable:
    """Register fn(path, text, live=False) -> list of problems for files matching an extension, name or glob."""

    def deco(fn):
        HANDLERS[name] = {
            "label": label or name,
            "exts": tuple(e.lower() for e in exts),
            "names": tuple(n.lower() for n in names),
            "globs": tuple(globs),
            "fn": fn,
        }
        return fn

    return deco


def _matches(h: dict, path: str) -> bool:
    base = os.path.basename(path).lower()
    norm = path.replace("\\", "/")
    return (
        (bool(h["exts"]) and base.endswith(h["exts"]))
        or base in h["names"]
        or any(fnmatch.fnmatch(norm, g) for g in h["globs"])
    )


def inspect_text(path: str, text: str, live: bool = False) -> dict:
    """Run every matching handler. Returns {"kinds": [...], "problems": [...], "notes": [...]}."""
    kinds, problems, notes = [], [], []
    for name, h in list(HANDLERS.items()):
        if not _matches(h, path):
            continue
        kinds.append(h["label"])
        try:
            found = h["fn"](path, text, live) or []
        except Exception as e:  # a faulty user handler must not break the editor
            found = [problem(f"the {name} checker failed: {e}", level="warning")]
        for item in found:
            if isinstance(item, str):
                notes.append(item)
            else:
                problems.append(item)
    problems.sort(key=lambda x: (x["line"], x["col"]))
    return {
        "kinds": kinds,
        "problems": problems,
        "notes": notes,
        "ok": not any(p["level"] == "error" for p in problems),
    }


def _tool(args: list[str], text: str, suffix: str, timeout: int = 15) -> tuple[int, str]:
    """Run a syntax-check tool on a temporary copy of the text."""
    fd, tmp = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        r = subprocess.run(
            [*args, tmp],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            creationflags=plat.NO_WINDOW,
        )
        return r.returncode, ((r.stderr or "") + (r.stdout or "")).replace(tmp, "file")
    except (OSError, subprocess.SubprocessError) as e:
        return 127, str(e)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


@file_handler("python", exts=[".py", ".pyw"], label="Python")
def _python(path, text, live=False):
    try:
        compile(text, path, "exec", dont_inherit=True)
    except SyntaxError as e:
        return [problem(e.msg, e.lineno, e.offset)]
    except ValueError as e:
        return [problem(str(e))]
    return []


@file_handler("json", exts=[".json", ".webmanifest"], label="JSON")
def _json(path, text, live=False):
    try:
        json.loads(text or "null")
    except json.JSONDecodeError as e:
        return [problem(e.msg, e.lineno, e.colno)]
    return []


@file_handler("xml", exts=[".xml", ".svg", ".xsd", ".plist"], label="XML")
def _xml(path, text, live=False):
    try:
        ElementTree.fromstring(text.encode("utf-8"))
    except ElementTree.ParseError as e:
        line, col = e.position
        return [problem(str(e).split(":")[0], line, col)]
    return []


@file_handler("toml", exts=[".toml"], label="TOML")
def _toml(path, text, live=False):
    try:
        import tomllib
    except ImportError:
        return ["TOML is checked on Python 3.11 or newer."]
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        m = re.search(r"line (\d+), column (\d+)", str(e))
        return [problem(str(e), *(m.groups() if m else (0, 0)))]
    return []


@file_handler("ini", exts=[".ini", ".cfg"], names=["php.ini", "my.cnf", "setup.cfg"], label="INI")
def _ini(path, text, live=False):
    parser = configparser.RawConfigParser(strict=False, interpolation=None, allow_no_value=True)
    try:
        parser.read_string(text)
    except configparser.MissingSectionHeaderError as e:
        return [problem("a setting appears before any [section]", e.lineno)]
    except configparser.ParsingError as e:
        return [problem("cannot parse this line", ln) for ln, _ in e.errors] or [problem(str(e))]
    except configparser.Error as e:
        return [problem(str(e))]
    return []


_UNIT = re.compile(r"^\s*(\[[A-Za-z][\w-]*\]|[A-Za-z][\w.-]*\s*=.*|[#;].*|)$")


@file_handler("systemd", exts=[".service", ".socket", ".timer", ".mount", ".target", ".path"], label="systemd unit")
def _systemd(path, text, live=False):
    out, in_section, cont = [], False, False
    for n, line in enumerate(text.splitlines(), 1):
        if not cont:
            if not _UNIT.match(line):
                out.append(problem("expected [Section], Key=Value or a comment", n))
            elif re.match(r"^\s*\[", line):
                in_section = True
            elif "=" in line and not line.lstrip().startswith(("#", ";")) and not in_section:
                out.append(problem("setting before the first [Section]", n))
        cont = line.rstrip().endswith("\\")
    if live and not plat.IS_WIN and plat.which("systemd-analyze") and not out:
        rc, msg = _tool(["systemd-analyze", "verify"], text, os.path.splitext(path)[1] or ".service")
        out += [problem(m.strip(), level="warning") for m in msg.splitlines() if m.strip()][:10]
    return out


@file_handler("env", exts=[".env"], names=[".env", "environment"], globs=["*/.env.*"], label="Environment file")
def _env(path, text, live=False):
    return [
        problem("expected KEY=value or a comment", n)
        for n, line in enumerate(text.splitlines(), 1)
        if line.strip()
        and not line.lstrip().startswith("#")
        and not re.match(r"^\s*(export\s+)?[A-Za-z_]\w*\s*=", line)
    ]


@file_handler("yaml", exts=[".yml", ".yaml"], label="YAML")
def _yaml(path, text, live=False):
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        if re.match(r"^ *\t", line):
            out.append(problem("YAML does not allow tabs for indentation", n))
    return out


@file_handler("shell", exts=[".sh", ".bash"], names=[".bashrc", ".profile", ".bash_profile", ".zshrc"], label="Shell")
def _shell(path, text, live=False):
    sh = plat.which("bash") or plat.which("sh")
    if not sh:
        return ["bash was not found, so shell syntax cannot be checked here."]
    rc, msg = _tool([sh, "-n"], text, ".sh")
    found = [problem(m.group(2).strip(), m.group(1)) for m in re.finditer(r"line (\d+): (?!`)(.+)", msg)]
    return found or ([problem(msg.strip()[:300])] if rc and msg.strip() else [])


@file_handler("javascript", exts=[".js", ".mjs", ".cjs"], label="JavaScript")
def _js(path, text, live=False):
    node = plat.which("node")
    if not node:
        return ["node was not found, so JavaScript syntax cannot be checked here."]
    rc, msg = _tool([node, "--check"], text, os.path.splitext(path)[1] or ".js")
    if not rc:
        return []
    m = re.search(r"file:(\d+)", msg)
    detail = next((x for x in msg.splitlines() if "Error" in x), msg.strip()[:200])
    return [problem(detail, m.group(1) if m else 0)]


@file_handler("php", exts=[".php"], label="PHP")
def _php(path, text, live=False):
    php = plat.which("php")
    if not php:
        return ["php was not found, so PHP syntax cannot be checked here."]
    rc, msg = _tool([php, "-l"], text, ".php")
    if not rc:
        return []
    m = re.search(r"on line (\d+)", msg)
    return [
        problem(
            re.sub(r"^\s*(PHP )?Parse error:\s*", "", msg.splitlines()[0] if msg else "syntax error"),
            m.group(1) if m else 0,
        )
    ]


@file_handler("nginx", names=["nginx.conf"], globs=["*/nginx/*.conf", "*/nginx/*/*", "*/nginx/*/*/*"], label="nginx")
def _nginx(path, text, live=False):
    out, depth = [], 0
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        depth += line.count("{") - line.count("}")
        if depth < 0:
            out.append(problem("unexpected }", n))
            depth = 0
        elif line and not line.endswith((";", "{", "}")) and not line.startswith(("}", "#")):
            out.append(problem("directive is missing its closing ;", n))
    if depth > 0:
        out.append(problem(f"{depth} block(s) are not closed with }}"))
    if live and not out and plat.which("nginx"):
        try:
            r = subprocess.run(["nginx", "-t"], capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL)
            for m in (r.stderr or "").splitlines():
                if "[emerg]" in m or "[warn]" in m:
                    hit = re.search(r"\.(?:conf)?:(\d+)", m)
                    out.append(
                        problem(
                            m.split("]", 1)[-1].strip(),
                            hit.group(1) if hit else 0,
                            level="error" if r.returncode else "warning",
                        )
                    )
        except (OSError, subprocess.SubprocessError):
            pass
    return out
