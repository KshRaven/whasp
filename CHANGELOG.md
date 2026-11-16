# Changelog

## Unreleased

## 0.1.0
- Added a Firewall (WAF) extension under Security: request rules for SQL injection, script injection, path traversal, bad agents, geo and IP lists, with a rule tester and a generated nginx snippet applied after `nginx -t`.
- Added Tamper protection under Security: snapshots protected folders, scans them on a schedule (`tamper_interval`, minutes) and raises a notification for added, removed or changed files; optional `chattr +i` locking on Linux.
- Added Analytics under Websites: visitors, pages, referrers, errors, bots and daily requests from nginx/Apache access logs, with no tracking script.
- Changed the sign-in page to a single "W.H.A.S.P" card with username, password and the optional second step, with no marketing text.
- Added panel self-update: `whasp.system.updater` checks PyPI once a day (setting `update_check`), notifies when a newer release exists and upgrades through a Task (settings backup, `pip install whasp==X`, version check, automatic restart). Settings has a new Updates tab and the sidebar version shows an arrow when an update is available. New routes: `/api/update`, `/api/update/check`, `/api/update/install`.
- Added `tests/test_update.py` for version ordering, the update check, the job plan, the update API and the sign-in page.
- Renamed the project to Whasp: the Python package, the `whasp` command, `WHASP_*` variables, the service unit, the nginx example and the web interface identifiers.
- Added PyPI packaging: a `whasp/_version.py` version file, a `py.typed` marker, a source manifest and project metadata with links.
- Added `pypimgr` release tooling in `scripts/pypimgr` (build, verify, tag and publish from the command line or a guided menu).
- Added GitHub workflows: CI on Linux and Windows, and a release workflow that builds, creates a GitHub release and publishes to TestPyPI and PyPI.
- Added repository documents and templates: changelog, contributing guide, security policy, code of conduct, support notes, issue and pull request templates, Dependabot settings and an editor config.
- Reorganised the repository into packages: `core`, `auth`, `system`, `software`, `server`, `deploy`, `cli`, `tui` and `extensions`, with `__all__`, `from __future__ import annotations` and sorted imports in every module.
- Moved the install, development and maintenance scripts into `scripts/install`, `scripts/dev` and `scripts/maintenance`, and the systemd unit and nginx example into `contrib/`.
- Added `whasp setup` network modes (local, intranet, IP-only reverse proxy, self-signed HTTPS, domain with certificate) and the `email` setting for certificate notices.
- Added an admin username and password prompt to `service install`, with `--admin-user`, `--admin-password` and `--no-prompt`.
- Changed the file manager to open in a default folder created by `whasp init` (`file_start`), browse the whole system as root or Administrator with a Quick access list, protect system folders from delete, rename and move, and check files while editing (Python, JSON, XML, TOML, INI, YAML, systemd, `.env`, shell, JavaScript, PHP, nginx) with optional `.bak` backups and a hook for extension-defined file types.
- Added `whasp self-install`, which installs the package system-wide in `/opt/whasp` and links `/usr/local/bin/whasp` so `sudo whasp` works.
- Changed the default look to a yellow-orange "wasp" accent and a near-black dark theme.
- Baseline: web panel, terminal app, CLI, software catalog, built-in extensions (Files, Websites, Docker, Databases, Logs, Processes, Tasks, Firewall, Security, Backups, Services, Desktop), optional MFA and user extensions.
