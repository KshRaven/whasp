"""Self-update pipeline and the minimal sign-in page."""

from __future__ import annotations

import sys
import unittest

import helpers  # noqa: F401  (sets WHASP_HOME to a throwaway folder before whasp is imported)
from helpers import http, jhttp, start
from whasp import __version__
from whasp.auth import mfa
from whasp.core.errors import PanelError
from whasp.system import jobs, updater


class Versions(unittest.TestCase):
    def test_ordering(self):
        self.assertTrue(updater.newer("0.1.2", "0.1.0"))
        self.assertTrue(updater.newer("0.10.0", "0.9.9"))
        self.assertFalse(updater.newer("0.1.0", "0.1.0"))
        self.assertFalse(updater.newer("0.0.9", "0.1.0"))
        self.assertFalse(updater.newer("0.1.0rc1", "0.1.0"))  # a pre-release is older than its final release
        self.assertTrue(updater.newer("1.0", "0.9.9"))
        self.assertFalse(updater.newer("", "0.1.0"))


class Check(unittest.TestCase):
    def setUp(self):
        start()
        self._fetch = updater._fetch
        updater._file().unlink(missing_ok=True)

    def tearDown(self):
        updater._fetch = self._fetch
        updater._file().unlink(missing_ok=True)

    def test_finds_newer_release(self):
        updater._fetch = lambda: "99.0.0"
        st = updater.check(force=True)
        self.assertTrue(st["available"])
        self.assertEqual(st["latest"], "99.0.0")
        self.assertEqual(updater.status()["latest"], "99.0.0")  # cached for the status route

    def test_network_error_is_reported_not_raised(self):
        def boom():
            raise OSError("offline")

        updater._fetch = boom
        st = updater.check(force=True)
        self.assertFalse(st["available"])
        self.assertIn("PyPI", st["error"])

    def test_cache_skips_the_network(self):
        updater._fetch = lambda: "99.0.0"
        updater.check(force=True)
        updater._fetch = lambda: self.fail("should use the cache")
        self.assertEqual(updater.check()["latest"], "99.0.0")


class Plan(unittest.TestCase):
    def test_steps(self):
        title, steps, env = updater.plan("99.0.0", lambda: None)
        self.assertEqual(title, "Update whasp to 99.0.0")
        argvs = [s if isinstance(s, list) else s["cmd"] for s in steps if not callable(s)]
        pip = next(a for a in argvs if "install" in a)
        self.assertEqual(pip[:3], [sys.executable, "-m", "pip"])
        self.assertIn("whasp==99.0.0", pip)
        self.assertTrue(callable(steps[0]) and callable(steps[-1]))  # backup first, restart last
        self.assertEqual(env["PIP_NO_INPUT"], "1")

    def test_same_version_refused(self):
        with self.assertRaises(PanelError):
            updater.plan(__version__, lambda: None)

    def test_install_version_validation(self):
        self.assertEqual(updater.install_version("0.2.0"), "0.2.0")
        for bad in ("1.0; rm -rf /", "x", "1.0 --index-url http://evil"):
            with self.assertRaises(PanelError):
                updater.install_version(bad)


class Api(unittest.TestCase):
    def setUp(self):
        start()
        self.token = mfa.login("tester", "test-password-1")["session"]  # other tests revoke the shared one
        self._fetch, self._start = updater._fetch, jobs.start
        updater._fetch = lambda: "99.0.0"

    def tearDown(self):
        updater._fetch, jobs.start = self._fetch, self._start
        updater._file().unlink(missing_ok=True)

    def test_requires_sign_in(self):
        self.assertEqual(jhttp("/api/update")[0], 401)
        self.assertEqual(jhttp("/api/update/install", "POST", {"version": "99.0.0"})[0], 401)

    def test_check_and_install_start_a_task(self):
        code, st = jhttp("/api/update/check", "POST", {}, bearer=self.token)
        self.assertEqual((code, st["available"]), (200, True))
        started = {}

        class Fake:
            id = 7

        def fake_start(title, steps, **kw):
            started.update(title=title, kind=kw.get("kind"))
            return Fake()

        jobs.start = fake_start
        code, r = jhttp("/api/update/install", "POST", {"version": "99.0.0"}, bearer=self.token)
        self.assertEqual(code, 200)
        self.assertEqual(r["job"], 7)
        self.assertEqual(started, {"title": "Update whasp to 99.0.0", "kind": "install"})

    def test_me_reports_update(self):
        updater.check(force=True)
        code, me = jhttp("/api/me", bearer=self.token)
        self.assertTrue(me["update"]["available"])

    def test_bad_version_rejected(self):
        code, r = jhttp("/api/update/install", "POST", {"version": "1;ls"}, bearer=self.token)
        self.assertEqual(code, 400)


class LoginPage(unittest.TestCase):
    def test_page_is_minimal(self):
        code, body, _ = http("/")
        html = body.decode()
        self.assertEqual(code, 200)
        self.assertIn("W.H.A.S.P", html)
        for gone in (
            "Welcome back",
            "calm place",
            "administrator account you created",
            "Nothing is loaded from other sites",
        ):
            self.assertNotIn(gone, html)
        self.assertNotIn("art-points", html)


if __name__ == "__main__":
    unittest.main()
