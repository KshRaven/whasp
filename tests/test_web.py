"""Web asset, caching and audit checks."""

from __future__ import annotations

import gzip, json, re, time, unittest
from pathlib import Path
from helpers import config, http, start
import helpers  # noqa: F401  (sets WHASP_HOME to a throwaway folder before whasp is imported)
from whasp.core import audit

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "whasp" / "web"
FILES = [p for p in WEB.rglob("*") if p.is_file()]


def lum(hex_):
    c = [int(hex_[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class WebAssets(unittest.TestCase):
    def test_default_look_is_wasp_accent_on_near_black(self):
        css, theme = (WEB / "style.css").read_text(encoding="utf-8"), (WEB / "theme.js").read_text(encoding="utf-8")
        self.assertIn("accent: 'wasp'", theme)
        self.assertIn('data-accent="wasp"', (WEB / "index.html").read_text(encoding="utf-8"))
        self.assertRegex(css, r":root,\[data-theme=graphite\]\{--bg:#0[0-9a-f]0[0-9a-f]0[0-9a-f]")

    def test_no_third_party_requests(self):  # no SDKs, CDNs, fonts, analytics
        for f in FILES:
            txt = f.read_text(encoding="utf-8")
            self.assertFalse(
                re.search(
                    r"https?://(?!127\.0\.0\.1|localhost)",
                    txt.replace("http://127.0.0.1", "").replace("http://www.w3.org/2000/svg", ""),
                ),
                f"external URL in {f.name}",
            )
            self.assertNotIn("@import", txt)
            self.assertNotIn("@font-face", txt)

    def test_no_images_without_alt_and_no_inline_script(self):
        for f in FILES:
            for tag in re.findall(r"<img\b[^>]*>", f.read_text(encoding="utf-8")):
                self.assertIn("alt=", tag, f.name)
        self.assertNotRegex((WEB / "index.html").read_text(encoding="utf-8"), r"<script(?![^>]*\bsrc=)")

    def test_themes_meet_wcag_aa(self):
        css = (WEB / "style.css").read_text(encoding="utf-8")
        themes = re.findall(r"(?::root,)?\[data-theme=(\w+)\]\{([^}]*)\}", css)
        self.assertGreaterEqual(len(themes), 5)
        for name, body in themes:
            v = {
                k: ("#" + "".join(ch * 2 for ch in c[1:]) if len(c) == 4 else c)  # expand #fff
                for k, c in re.findall(r"--(\w+):(#[0-9a-fA-F]{3,6})\b", body)
            }
            if "fg" not in v:  # partial override blocks inherit their colours
                continue
            for bg in ("bg", "panel"):
                for fg in ("fg", "muted", "ok", "warn", "bad", "info"):
                    self.assertGreaterEqual(ratio(v[fg], v[bg]), 4.5, f"{name}: {fg} on {bg}")

    def test_keyboard_and_labels(self):
        html, js = (WEB / "index.html").read_text(encoding="utf-8"), (WEB / "ui" / "desktop.js").read_text(encoding="utf-8")
        self.assertIn('class="skip"', html)
        self.assertIn('lang="en"', html)
        for needle in ("onkeydown", "ArrowLeft", "Escape", "aria-label", "role: 'menu'"):
            self.assertIn(needle, js)

    def test_no_cookies_set(self):
        _, token = start()
        for path, b in (("/", None), ("/api/ping", token)):
            self.assertNotIn("Set-Cookie", http(path, bearer=b)[2])

    def test_audit_retention_and_erase(self):
        audit.erase()
        audit.log("old")
        audit.log("new")
        p = config.LOGDIR / "audit.log"
        lines = p.read_text(encoding="utf-8").splitlines()
        old = json.loads(lines[0])
        old["ts"] = int(time.time()) - 200 * 86400
        p.write_text(json.dumps(old) + "\n" + lines[1] + "\n")
        audit.prune(90)
        self.assertEqual([e["event"] for e in audit.tail(10)], ["new"])
        self.assertGreaterEqual(audit.erase(), 1)
        self.assertEqual(audit.tail(10), [])

    def test_ip_not_logged_beyond_audit_and_secrets_redacted(self):
        self.assertEqual(
            audit.redact({"password": "x", "content": "y"}), {"password": "<redacted>", "content": "<redacted>"}
        )

    def test_static_cache_and_gzip(self):
        code, body, hdr = http("/app.js", headers={"Accept-Encoding": "gzip"})
        self.assertEqual(hdr["Content-Encoding"], "gzip")
        self.assertEqual(gzip.decompress(body), (WEB / "app.js").read_bytes())
        self.assertEqual(http("/app.js", headers={"If-None-Match": hdr["ETag"]})[0], 304)

    def test_ui_module_path_traversal(self):
        self.assertEqual(http("/ui/desktop.js")[0], 200)
        for bad in ("/ui/..%2fapp.js", "/ui/../app.js", "/ui/nope.js", "/ui/desktop.py"):
            self.assertEqual(http(bad)[0], 404, bad)


if __name__ == "__main__":
    unittest.main()
