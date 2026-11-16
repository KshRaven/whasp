from __future__ import annotations
import os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import helpers  # noqa: F401  (sets WHASP_HOME to a throwaway folder before whasp is imported)
from whasp.core import config
from whasp import deploy
from whasp.deploy import service
from whasp.core import plat  # noqa: E402
from whasp.server import sitehost  # noqa: E402
from whasp.extensions import websites  # noqa: E402


class UserService(unittest.TestCase):
    def test_user_defaults_use_writable_website_root(self):
        with patch.object(plat, "IS_WIN", False), patch.object(plat, "IS_ROOT", False):
            defaults = plat.defaults(Path(".whasp"))

        self.assertEqual(defaults["web_roots"], [str(Path.home() / "www")])
        self.assertEqual(defaults["file_roots"], [str(Path.home() / "www"), str(Path.home())])
        self.assertEqual(defaults["file_start"], str(Path.home() / "www"))

    def test_system_defaults_browse_the_whole_server_and_start_in_the_web_root(self):
        with patch.object(plat, "IS_WIN", False), patch.object(plat, "IS_ROOT", True):
            defaults = plat.defaults(Path("/etc/whasp"))

        self.assertEqual(defaults["file_roots"], ["/"])
        self.assertEqual(defaults["file_start"], "/var/www")

    def test_windows_user_defaults_avoid_system_website_directories(self):
        with patch.object(plat, "IS_WIN", True), patch.object(plat, "IS_ROOT", False):
            defaults = plat.defaults(Path(".whasp"))

        self.assertEqual(defaults["web_roots"], [str(Path.home() / "www")])
        self.assertEqual(defaults["file_start"], str(Path.home() / "www"))

    def test_user_domain_url_includes_builtin_port(self):
        with (
            patch.dict(
                config.cfg, {"domain": "panel.example.com", "site_port": 8080, "site_engine": "auto", "port": 8800}
            ),
            patch.object(plat, "IS_ROOT", False),
        ):
            info = deploy.domain_info()

        self.assertEqual(info["urls"][0], "http://panel.example.com:8080/")

    def test_user_websites_do_not_require_nginx_access(self):
        with patch.object(plat, "IS_ROOT", False):
            self.assertTrue(websites._builtin())

    def test_running_user_host_reloads_sites_saved_by_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            sites_file = Path(tmp) / "sites.json"
            sites_file.write_text('{"panel.example.com": {"domain": "panel.example.com"}}', encoding="utf-8")
            with (
                patch.object(sitehost, "FILE", sites_file),
                patch.object(sitehost, "_mtime", 0),
                patch.object(sitehost, "_sites", {}),
                patch.object(sitehost, "ensure") as ensure,
            ):
                sitehost.reload_if_changed()
                self.assertIn("panel.example.com", sitehost._sites)
                ensure.assert_called_once()

    def test_user_service_install_needs_no_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            unit = Path(tmp) / "systemd" / "user" / "whasp.service"
            with (
                patch.object(service, "USER_UNIT", unit),
                patch.object(plat, "IS_WIN", False),
                patch.object(plat, "IS_ROOT", False),
                patch.object(plat, "has_systemd", return_value=True),
                patch.object(service, "_run", return_value=(0, "")) as run,
            ):
                result = deploy.service_install()

            self.assertIn("user whasp.service", result["message"])
            text = unit.read_text(encoding="utf-8")
            self.assertIn("WantedBy=default.target", text)
            self.assertIn(f"ExecStart={service._systemd_quote(sys.executable)} -m whasp web", text)
            self.assertIn("WHASP_HOME=", text)
            self.assertEqual(run.call_args_list[-1].args[0], ["systemctl", "--user", "enable", "--now", "whasp"])


if __name__ == "__main__":
    unittest.main()
