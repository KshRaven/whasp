"""Setup modes, nginx rendering and the settings that belong to them (no root, no network, nothing installed)."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers  # noqa: E402,F401  (sets WHASP_HOME to a throwaway folder before whasp is imported)

from whasp import deploy  # noqa: E402
from whasp.core import config  # noqa: E402
from whasp.core.errors import PanelError  # noqa: E402


class NginxRender(unittest.TestCase):
    def test_ip_mode_answers_any_host_on_port_80(self):
        text = deploy.render_nginx(port=8800)
        self.assertIn("server_name _;", text)
        self.assertIn("listen 80 default_server;", text)
        self.assertIn("server 127.0.0.1:8800;", text)
        self.assertIn("$http_host", text)

    def test_domain_with_certificate_redirects_http_to_https(self):
        text = deploy.render_nginx("panel.example.com", 8800, "/c.crt", "/c.key", 8080, 8443)
        self.assertIn("return 301 https://$host:8443$request_uri;", text)
        self.assertIn("listen 8443 ssl;", text)
        self.assertNotIn("default_server", text)

    def test_bad_domain_is_refused(self):
        with self.assertRaises(PanelError):
            deploy.render_nginx("bad domain;")


class SetupChecks(unittest.TestCase):
    def check(self, **kw):
        deploy.setup._check(deploy.SetupOptions(**kw))

    def test_domain_mode_needs_a_domain(self):
        with self.assertRaises(PanelError):
            self.check(mode="domain")

    def test_certbot_needs_a_domain(self):
        with self.assertRaises(PanelError):
            self.check(mode="proxy", certbot=True)

    def test_allow_must_be_an_address_range(self):
        with self.assertRaises(PanelError):
            self.check(mode="lan", allow=["not-a-range"])
        self.check(mode="lan", allow=["192.168.1.0/24"])

    def test_local_mode_rejects_lan_only_options(self):
        with self.assertRaises(PanelError):
            self.check(mode="local", self_signed=True)


class Settings(unittest.TestCase):
    def test_email_is_validated(self):
        self.assertEqual(config.validate_setting("email", " you@example.com "), "you@example.com")
        with self.assertRaises(ValueError):
            config.validate_setting("email", "nope")

    def test_proxy_settings_have_safe_defaults(self):
        self.assertFalse(config.DEFAULTS["trust_proxy"])
        self.assertEqual(config.DEFAULTS["email"], "")


if __name__ == "__main__":
    unittest.main()
