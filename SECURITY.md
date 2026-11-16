# Security

Whasp runs commands, manages services and edits files with the privileges of the account it runs as (root on Linux, SYSTEM on Windows when installed as a service). Do not expose it directly to an untrusted network: bind it to loopback and use an SSH tunnel, or put it behind HTTPS and restrict access. Use a strong admin password, enable MFA, and disable the command console (`whasp config set console_enabled false`) if you do not need it. Details are in [docs/SECURITY.md](docs/SECURITY.md).

To report a vulnerability, use [GitHub's private vulnerability reporting](https://github.com/KshRaven/whasp/security/advisories/new) rather than a public issue. You will get a reply within a few days.
