# Writing Extensions

An extension is a Python module exposing `EXT = Extension(...)`. It can register API routes and declarative GUI sections. Built-ins live in `whasp/extensions/`; user extensions are loaded from `<config directory>/extensions/*.py`. Extensions run in-process with the full privileges of the Whasp process. Review code before installing it.

```python
from whasp.extensions import Extension
from whasp.shell import run, need, NAME

EXT = Extension("redis", "Redis", "box", order=75, requires=["redis-cli"], description="Redis status and controls")


@EXT.route("info")
def info(params):
    return {"text": run(["redis-cli", "info", "server"], check=True)[1]}


@EXT.route("flush", write=True)
def flush(params):
    run(["redis-cli", "flushdb"], check=True)
    return {"ok": True}


EXT.sections = [
    {"type": "text", "title": "Server info", "source": "info"},
    {
        "type": "form",
        "title": "Flush database",
        "route": "flush",
        "submit": "Flush DB",
        "confirm": "Delete all keys?",
        "danger": True,
        "fields": [],
    },
]
```

Copy the file to the active config directory's `extensions` folder, then restart Whasp. The directory is `/etc/whasp/extensions` for root on Linux, `%ProgramData%\whasp\extensions` for an elevated Windows install, or `~/.whasp/extensions` for an unprivileged user unless `WHASP_HOME` is set. On Linux, extension files must be owned by the panel user and not group/world-writable. On Windows, symbolic links are refused and the config directory ACL should protect the files. Disable an extension by adding its name to `disabled_extensions`.

## Routes

- A route function receives one dictionary of parameters. HTTP GET parameters come from the query string; POST parameters come from a JSON object.
- Treat every parameter as untrusted. Validate strings with `need(value, regex, "description")` and use the provided validators such as `NAME` where appropriate.
- Mark every side-effecting route with `write=True`. This makes the HTTP handler require POST and records the action in the audit log. A route not marked `write=True` is not automatically audited.
- Return JSON-serializable values, or `Raw(data, content_type, filename)` for a file download.
- Raise `PanelError("message", status)` for expected errors. Unexpected exceptions are returned as a generic 500 and written to the panel log.
- Use `run([...])` for subprocesses. It resolves configured executable paths and avoids shell parsing; do not construct shell commands from route parameters.
- `whasp call EXT ROUTE key=value` invokes the route locally in the current OS process, without web authentication. It still audits routes marked as writes.

## Declarative UI Sections

Set `EXT.sections` to a list, or to a function that returns the list when the page is opened. Supported section `type` values:

| Type | Main properties |
|---|---|
| `stats` | `items` for static values or `source` route; optional `refresh` |
| `notice` | `title`, `text`, `level`, optional `actions` |
| `help` | `title`, `text`, optional `steps` and `example` |
| `table` | `title`, `source`, `columns`, optional `actions`, `buttons`, `refresh`, search/sort options |
| `form` | `title`, `route`, `method` (defaults to POST), `submit`, `fields`, optional `confirm` and `danger` |
| `text` | `title`, `source` route returning `{"text": "..."}` |
| `kv` | `title`, `source` route returning pairs or key/value data |
| `catalog` | Software catalog view with `source` and optional `detail`, `install`, and `uninstall` routes |
| `tabs` | `tabs`, each with an `id`, `title`, and its own `sections` list |
| `files` | Built-in file manager view |

Table columns may be `[label, key, format]`; formats include `bytes`, `time`, `ago`, `state`, `num`, `pct`, `mono`, `code`, `bool`, `list`, `level`, and `dur`. A row action can define `label`, `route`, `params`, `method`, `confirm`, `danger`, `download`, `form`, `filename`, `if`, and `ifnot`. `$key` placeholders in action strings are filled from the current row. A response containing `{"text": "..."}` is displayed as text; a response with a `job` value is followed in the console.

Form field types include `text`, `number`, `password`, `select`, `textarea`, and `checkbox`; `required`, `options`, `placeholder`, `value`, `min`, `max`, `rows`, and `help` are supported as applicable.

## Custom UI Modules

For a page that does not fit the built-in section types, an extension may set `ui="name"` and register `window.WHASP_UI.name = (view, ext, WHASP) => { ... }`. The module is served from `whasp/web/ui/name.js` and loaded only when its tab opens. This mechanism is for modules shipped in the application; user extensions cannot upload arbitrary web assets through the extensions directory. Existing modules such as `whasp/web/ui/desktop.js` show the integration pattern.

## File type checks

The file manager editor runs checks on the text being edited. To add one for another file type, register a handler from an extension:

```python
from whasp.extensions.filetypes import file_handler


@file_handler("caddy", names=["Caddyfile"], label="Caddyfile")
def check_caddy(path, text, live=False):
    # return a list of problems; live=True means the user asked to also run the real tool on the saved file
    return [{"line": 3, "col": 0, "level": "error", "message": "unknown directive"}] if "bogus" in text else []
```

Match files with `exts=[".ext"]`, `names=["exact-name"]` or `globs=["*/dir/*.conf"]`. Built in: Python, JSON, XML, TOML, INI, YAML, systemd units, `.env`, shell, JavaScript, PHP and nginx.
