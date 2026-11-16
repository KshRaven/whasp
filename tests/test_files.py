"""File manager: start folder, quick places, protected system folders and the editor checks."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers  # noqa: E402,F401  (sets WHASP_HOME to a throwaway folder before whasp is imported)

from whasp.core import config  # noqa: E402
from whasp.core.errors import PanelError  # noqa: E402
from whasp.extensions import files  # noqa: E402
from whasp.extensions.filetypes import file_handler, inspect_text  # noqa: E402


class StartAndPlaces(unittest.TestCase):
    def setUp(self):
        self.saved = {k: config.cfg.get(k) for k in ("file_roots", "file_start")}
        self.root = os.path.realpath(helpers.TMP)

    def tearDown(self):
        config.cfg.update(self.saved)

    def test_opens_at_file_start_when_it_is_inside_a_root(self):
        sub = os.path.join(self.root, "start")
        os.makedirs(sub, exist_ok=True)
        config.cfg.update(file_roots=[self.root], file_start=sub)
        self.assertEqual(files.places({})["start"], os.path.realpath(sub))

    def test_falls_back_to_the_first_root(self):
        config.cfg.update(file_roots=[self.root], file_start=os.path.join(self.root, "missing"))
        self.assertEqual(files.places({})["start"], self.root)

    def test_system_root_lists_the_filesystem_and_marks_it_protected(self):
        if os.name == "nt":
            self.skipTest("POSIX paths")
        config.cfg.update(file_roots=["/"], file_start="/")
        self.assertTrue(files.places({})["system"])
        self.assertTrue(files._protected("/etc"))
        with self.assertRaises(PanelError):
            files.delete({"path": "/etc"})


class Checks(unittest.TestCase):
    def kinds(self, path, text):
        return inspect_text(path, text)

    def test_python_error_has_a_line(self):
        r = self.kinds("/srv/app.py", "x = 1\ndef f(:\n")
        self.assertFalse(r["ok"])
        self.assertEqual(r["problems"][0]["line"], 2)

    def test_valid_files_pass(self):
        self.assertTrue(self.kinds("/a/b.json", '{"a": 1}')["ok"])
        self.assertTrue(self.kinds("/a/b.py", "print(1)\n")["ok"])

    def test_nginx_missing_semicolon_and_unclosed_block(self):
        r = self.kinds("/etc/nginx/conf.d/site.conf", "server {\n  listen 80\n")
        messages = " ".join(p["message"] for p in r["problems"])
        self.assertIn("closing ;", messages)
        self.assertIn("not closed", messages)

    def test_systemd_unit_and_env(self):
        self.assertFalse(self.kinds("/etc/systemd/system/a.service", "[Unit]\nDescription=x\nnonsense here\n")["ok"])
        self.assertTrue(self.kinds("/srv/.env", "A=1\n# note\n")["ok"])

    def test_extensions_can_add_their_own_type(self):
        @file_handler("demo-type", exts=[".demo"], label="Demo")
        def _demo(path, text, live=False):
            return [{"line": 1, "col": 0, "level": "error", "message": "demo says no"}] if "bad" in text else []

        self.assertFalse(self.kinds("/x/a.demo", "bad")["ok"])
        self.assertEqual(self.kinds("/x/a.demo", "fine")["kinds"], ["Demo"])


if __name__ == "__main__":
    unittest.main()
