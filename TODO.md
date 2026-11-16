# TODO

## Windows / Windows Server validation

- [ ] Run `scripts/install/*.ps1`, `scripts/maintenance/doctor.ps1`, `scripts/dev/dev.ps1`, `scripts/dev/test.ps1`, and `scripts/dev/demo.ps1` on supported Windows 10/11 and Server versions.
- [ ] Verify the config-directory ACL created by `whasp init` and the trust checks for user extensions on Windows.
- [ ] Check the Security page's Windows-specific checks and document unsupported checks clearly.
- [ ] Verify service, firewall (`netsh advfirewall`), and Task Scheduler behavior on localized Windows installations.
- [ ] Verify Docker Desktop discovery, permissions, and container actions.
- [ ] Test upgrade, reboot, and uninstall behavior for the SYSTEM scheduled task.

## Later releases

- [ ] Multi-server management (one panel controlling several servers).
- [ ] Mobile app or a mobile-first layout.
- [ ] Translations of the web interface and CLI (the strings are currently English only).
- [ ] Windows: replace the in-use `whasp.exe` during self-update (pip may need the panel stopped first).

## Other validation and maintenance

- [ ] Exercise the WAF snippet, tamper scans and analytics parsing against real nginx/Apache logs on a disposable host.

- [ ] Exercise the optional Linux desktop install/start/stop flow on a disposable Debian or Ubuntu host.
- [ ] Review external examples and deployment references for the `whasp` name when publishing releases.
