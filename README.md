# Whasp

A personal server control panel with a web interface, CLI, and terminal UI. Requires Python 3.9+ on Linux or Windows. The application uses the Python standard library; Windows installs the `windows-curses` package for the terminal UI. The web interface has no build step or external frontend dependencies.

The panel manages services and software, websites, files, scheduled jobs, firewalls, containers, databases, backups, logs, processes, and security checks. It also includes monitoring, notifications, a command console, optional MFA, user extensions, and a web desktop.

## Repository Layout

```
whasp/                 the shipped Python package (pip install whasp -> `whasp`)
  core/                settings, platform and shell helpers, errors, audit log, formatting
  auth/                rate limiting, second factors (MFA)
  system/              monitor, background process, jobs, notifications, dashboard
  software/            installable software catalog
  server/              HTTP API and built-in website host
  deploy/              service, setup modes, nginx, TLS, domains, admin login
  cli/                 argument parser, app entry point, command groups
  tui/                 terminal app
  extensions/          built-in extensions (files, docker, firewall, ...)
  web/                 browser UI (no build step)
scripts/
  install/             install and uninstall for Linux and Windows
  dev/                 dev server, demo sandbox, test runner
  maintenance/         doctor, config backup
  pypimgr/             release tooling
contrib/               systemd unit and nginx example
docs/  examples/  experimental/  tests/
```

## Security First

The default listener is `0.0.0.0:8800` and uses plain HTTP unless TLS is configured. The command console is enabled by default and executes commands as the panel process account. The Linux installer runs the service as root; the Windows installer runs it as SYSTEM. Do not expose Whasp directly to an untrusted network. Bind it to loopback and use an SSH tunnel, or configure HTTPS and restrict network access. Disable the console with `whasp config set console_enabled false` if it is not needed. See [docs/SECURITY.md](docs/SECURITY.md).

## Interfaces and Features

- **Web panel**: live system dashboard, software library, notifications, settings, and management tabs. Supports six themes, five accent colors, three text sizes, and two density settings.
- **CLI**: manage the panel, inspect system state, install catalog software, and call extension routes.
- **Terminal UI**: dashboard, services and software, processes, notifications, and panel controls. On Windows it uses `windows-curses`.
- **Command console**: interactive shell running as the panel process account. It can be disabled in settings or configuration.
- **Extensions**: 12 built-in management extensions plus the dashboard and settings (Files, Websites, Docker, Databases, Logs, Processes, Tasks, Firewall, Security, Backups, Services, Desktop). Custom Python extensions can add API routes and declarative GUI sections.
- **Websites without nginx**: a built-in site host (static folders, reverse proxy, redirects by Host header, default port 8080) is used when nginx is not installed. HTTPS and WebSockets still need nginx.
- **Databases**: SQLite works everywhere; MySQL/MariaDB and PostgreSQL appear when installed and can be installed from the Services catalog.
- **E-mail**: Settings > E-mail holds the SMTP details and a test button; a mail server (Postfix, hMailServer) can be installed from the catalog.
- **Mapped address and domain**: the panel answers at `http://host:8800/whasp/` as well as the bare port (`base_path`), and can be launched at boot under a domain name (`whasp service install`, `whasp domain set`).
- **Optional Linux desktop session**: TigerVNC/noVNC, Openbox, and xterm installed only after confirmation and resource checks. The browser-based desktop works on Linux and Windows without those packages.

Some actions require system tools or elevated privileges. The UI reports missing tools; the Services page includes a software catalog for supported package managers.

## Quick Start

From PyPI (in a virtual environment or with `pipx`):

```bash
pipx install whasp        # or: python -m pip install whasp
whasp init
whasp web
```


From a development checkout, run on Linux/macOS shell:

```bash
./scripts/dev/dev.sh
```

On Windows, run `.\scripts\dev\dev.ps1`. If port 8800 is occupied, the script selects the next available port; specify one with `.\scripts\dev\dev.ps1 -Port 8801`.

This creates `.dev-home`, initializes an admin account, and starts the panel at port 8800. The generated password is printed once. To install from the project directory instead:

```bash
python3 -m venv .venv && . .venv/bin/activate    # needed on Debian/Ubuntu 23.04+ (PEP 668: "externally-managed-environment")
python -m pip install .
whasp init
whasp web
```

`pipx install .` works too. To install Whasp only for your own account, with no `sudo` and no system packages:

```bash
bash ./scripts/install/install.sh --user --port 8800
export PATH="$HOME/.local/bin:$PATH"   # needed in this shell; the installer also updates shell startup files
whasp start                              # or run in the foreground with: whasp web
```

The user install puts the application under `~/.local/share/whasp`, its private config and logs under `~/.config/whasp`, the default website root under `~/www`, and the `whasp` command under `~/.local/bin`. When run without arguments, `install.sh` selects this user install automatically if you are not root. `--with` is only for the system installer because installing operating-system packages requires administrator privileges. The optional `whasp service install` creates a systemd user service without sudo; to have it start before you log in, user lingering may need to be enabled by an administrator. Remove the user install with `bash ./uninstall.sh` (add `--purge` to also delete its configuration).

If `./scripts/install/install.sh` says "Permission denied" (a zip or Windows checkout drops the executable bit), run it through `bash` as shown above.

On first start, Whasp creates the `admin` account and prints a generated password if you have not run `whasp init`. Use `whasp passwd` to change it.

### Linux system install

The installer supports apt-based distributions with systemd:

```bash
sudo bash ./scripts/install/install.sh --port 8800 --with "nginx ufw fail2ban"
```

It installs Python and requested OS packages, installs the service under `/opt/whasp`, stores configuration under `/etc/whasp`, and starts the `whasp` systemd service as root. The generated admin password is printed during setup. The panel listens on all interfaces; configure HTTPS and firewall restrictions before remote use.

The user install uses the built-in website host on its unprivileged port (default `8080`) and can publish a domain with `whasp domain set panel.example.com`. Point DNS at the server and allow the configured port through the cloud firewall. Serving directly on standard ports 80/443, configuring nginx, or installing a system service remains an administrator-level operation; use a reverse proxy or provider port forwarding if you do not have that access.

### System-wide install from the package

```bash
pip install --user whasp
whasp self-install            # re-runs itself with sudo
sudo whasp service install    # start at boot
```

`whasp self-install` creates a root-owned runtime in `/opt/whasp` with this same Whasp version and links `whasp` into `/usr/local/bin`, so `sudo whasp ...` works even when Whasp was installed with `pip install --user` and sudo's PATH does not include it. It also creates the system config in `/etc/whasp`.

### Windows system install

Run elevated PowerShell. Install Python 3.9+ for all users first, or use `-InstallPython` when `winget` is available:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install\install.ps1 -Port 8800
```

The installer places the application under `%ProgramFiles%\Whasp`, uses `%ProgramData%\whasp` for configuration and logs, and registers the `WhaspPanel` scheduled task to run as SYSTEM. The panel listens on all interfaces. Windows behavior is not yet fully verified; see [TODO.md](TODO.md). Remove it with `uninstall.ps1`.

### Safe browser access

For local-only access, set the bind address and restart the panel:

```bash
whasp config set host 127.0.0.1
whasp restart
ssh -L 8800:127.0.0.1:8800 you@your-server
```

Then browse to `http://127.0.0.1:8800`. For remote access, use HTTPS with a reverse proxy or configure `tls_cert` and `tls_key` in Whasp, and apply an IP allowlist/firewall rule. Read [docs/SECURITY.md](docs/SECURITY.md) before exposing it.

## CLI

```text
whasp init [--user NAME] [--password PASSWORD] [--reset]  Create/reset the admin account
whasp web [--host HOST] [--port PORT] [--open]            Run in the foreground
whasp start | stop | restart                              Control the background panel (stop also ends the boot service)
whasp service [install|remove|status]                     Start the panel at boot (systemd / Task Scheduler)
whasp domain [set NAME|remove|show] [--persist]           Publish the panel under a domain name
whasp url | user                                          Print panel addresses / the admin user name
whasp passwd [--user NAME] [--password PASSWORD]          Change account credentials
whasp status | doctor | ext | services                    Inspect the system and extensions
whasp catalog                                             List software in the catalog
whasp install NAME | uninstall NAME                       Manage catalog software
whasp svc NAME start|stop|restart|reload|enable|disable   Manage a watched service
whasp call EXT ROUTE key=value                            Call an extension route locally
whasp config [show] | config set KEY VALUE                 Read or update configuration
whasp mfa [reset|test-email ADDRESS]                      Check or reset MFA
whasp privacy export|delete                               Export or delete selected data
whasp logs [-n COUNT] | notes [-n COUNT]                   Show audit events or notifications
whasp tui                                                 Open the full-screen terminal UI
```

`whasp call` invokes extension code directly in the local process, not through the web login. Run it only as a trusted OS account. See `whasp --help` for full options.

## Configuration

Configuration is stored in `$WHASP_HOME/config.json` when `WHASP_HOME` is set; otherwise `/etc/whasp` when running as root on Linux, `%ProgramData%\whasp` when elevated on Windows, or `~/.whasp` for an unprivileged user. Use `whasp config` to inspect it. Changes to ordinary settings are reloaded automatically; changing `host`, `port`, or TLS settings requires a panel restart.

| Setting | Default | Purpose |
|---|---|---|
| `host`, `port` | `0.0.0.0`, `8800` | Listener address and port |
| `tls_cert`, `tls_key` | empty | Certificate and key paths; both are needed for direct HTTPS |
| `allowed_ips` | `[]` | Optional client IP/network allowlist for API requests |
| `services`, `file_roots`, `web_roots`, `log_files` | OS-specific | Service allowlist and filesystem access roots (`file_roots` is `/` for root/Administrator, the web folder and home folder for a user) |
| `file_start` | `/var/www` (system), `~/www` (user) | Folder the file manager opens first; created by `whasp init` |
| `backup_dir`, `cron_user`, `bin_dirs`, `nginx_dir` | OS-specific | Backup location, job account, executable search paths, and nginx config path |
| `disabled_extensions` | `[]` | Extension names to hide/disable |
| `alerts` | CPU, memory, disk at 90% | Alert thresholds; set a value to 0 to disable it |
| `sample_interval`, `history_len` | `5`, `360` | Monitoring interval in seconds and retained sample count |
| `session_ttl_hours` | `8` | Session lifetime; range 0.25 to 720 hours |
| `console_enabled` | `true` | Enable the web command console |
| `audit_retention_days` | `90` | Prune older audit entries; 0 disables pruning |
| `base_path`, `domain` | `/whasp`, empty | Extra path the panel answers at, and the domain it is published under |
| `site_engine`, `site_port` | `auto`, `8080` | `auto` uses nginx if installed, else the built-in site host on `site_port`; `builtin` forces the built-in one |
| `job_concurrency` | `1` | Installs/updates run at once (1 = one after another, for small servers) |
| `smtp`, `desktop` | See defaults in `whasp/config.py` | Mail/MFA and optional Linux desktop settings |

Use JSON values when setting structured configuration, for example:

```bash
whasp config set file_roots '["/var/www","/srv"]'
```

## File Manager

The file manager opens in a default folder that `whasp init` creates (`~/www` for a user install, `/var/www` for a system install). Run as root or Administrator it can browse the whole server: the Quick access list jumps to the start folder, home, `/opt`, `/etc`, `/var/log`, `/srv` and so on. Run as a normal user it is limited to the web folder and the user's home. System folders such as `/etc` and `/usr` can be opened and edited but never deleted, renamed or moved.

The editor checks the file as you type (nothing is executed): Python, JSON, XML, TOML, INI, YAML, systemd units, `.env` files, shell, JavaScript, PHP and nginx configs. Tick "Keep a .bak backup" to save the previous version beside the file, and "Test with the real tool" to also run `nginx -t` or `systemd-analyze verify` on the saved file. Extensions can add checks for more file types; see [docs/EXTENSIONS.md](docs/EXTENSIONS.md).

## Multi-Factor Sign-In

The admin username and password are always the first step. Optionally enable an authenticator app (TOTP) and/or e-mail codes under Settings. TOTP follows RFC 6238 and rejects reused codes. E-mail codes require SMTP configuration, expire after 10 minutes, and allow five attempts. Test SMTP with `whasp mfa test-email you@example.com`; inspect status with `whasp mfa`. To reset factors from the server, run `whasp mfa reset`.

## Updates

Settings > Updates shows the installed and latest version on PyPI. whasp checks once a day (turn it off with the `update_check` setting) and sends a notification when a newer release exists. Pressing **Update** runs a Task: it copies `config.json` to `config.json.bak-<version>`, runs `python -m pip install whasp==<version>` with the interpreter the panel runs on (with `--user` when the install folder is not writable), checks the installed version and restarts the panel. Follow it in the Tasks tab of the console. Under systemd the service restarts itself; otherwise the panel re-runs itself. Major releases may need manual steps, which the changelog lists.

## Customization and Extensions

- Appearance preferences are saved in browser local storage.
- Place custom CSS at `<config directory>/custom.css`.
- Place trusted extension modules in `<config directory>/extensions/`; restart Whasp after adding or changing one.
- See [docs/EXTENSIONS.md](docs/EXTENSIONS.md) and [examples/hello_extension.py](examples/hello_extension.py).

## Testing

```bash
make test          # scripts/dev/test.sh; automated tests
make check         # Python and JavaScript syntax checks
make demo          # disposable local demo on port 8800
make test-docker   # optional Docker test harness
```

The tests cover authentication and MFA, file sandboxing, extension routes, backups, cron validation, audit retention, web assets, static assets, and optional desktop resource gates. The demo and test suite do not require a production server.

## Documentation and Limitations

- [docs/SECURITY.md](docs/SECURITY.md): deployment and security model
- [docs/EXTENSIONS.md](docs/EXTENSIONS.md): extension API and UI schema
- [experimental/](experimental/README.md): unfinished ideas (panel database framework); not part of the running panel
- [THIRD_PARTY.md](THIRD_PARTY.md): dependencies and external tools

Whasp is intended for a single trusted operator and has no separate user roles. The console and extensions inherit the panel process privileges. The Windows paths and optional Linux desktop installation still need additional real-system validation. The software catalog invokes real OS package managers and external tools; review actions before running them on important servers.
