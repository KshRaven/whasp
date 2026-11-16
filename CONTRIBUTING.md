# Contributing

```
pip install -e ".[dev]"
pytest
ruff check .
```

- The package lives at `whasp/` in the repository root; use relative imports inside it.
- `scripts/dev/test.sh` (or `scripts/dev/test.ps1` on Windows) also syntax-checks the web JavaScript when Node is installed.
- Keep the core on the Python standard library; the panel must install with a plain `pip install whasp`.
- Add a line under `## Unreleased` in `CHANGELOG.md` for user-visible changes.
- Releases: `python scripts/pypimgr/pypimgr.py release patch --push`.
