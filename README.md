# mdmd

mdmd is a read-only Markdown viewer for the Linux desktop. It shows a Markdown
file as formatted text, like the preview pane of a Markdown editor, without a
web browser or embedded browser engine. Footnotes open in a small popup beside
their marker, and you can adjust every element's appearance with a live preview.

- CommonMark plus GitHub-style tables, strikethrough, task lists, autolinks, and footnotes
- Numbered citations (`[1]`, `\[1\]`) that point at a closing "Sources" or
  "References" list also open as popups
- Find (Ctrl+F) with match highlighting, per-window zoom, and automatic reload when the file changes
- Themes: save your appearance settings under a name and switch between them
- Links never open anything: hover to see the address, right-click to copy it.
  Links to headings in the same file scroll to that heading.

## Requirements

- Linux (developed on Ubuntu 24.04)
- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)

Qt is installed by uv as a Python package; no system packages are needed.

## Install and run

```bash
git clone <this repository> mdmd
cd mdmd
uv sync
uv run mdmd                     # opens the launcher with your recent files
uv run mdmd notes.md other.md   # opens each file in its own window
```

To have an `mdmd` command available everywhere:

```bash
uv tool install .
mdmd notes.md
```

Each launch is its own mdmd process. All of them share your settings, themes, and
recent files, and applying settings in one restyles the windows of all of them.

## Using mdmd

| Action | Keys |
| --- | --- |
| Open a file | Ctrl+O |
| Reload | F5 |
| Find, next, previous | Ctrl+F, F3 or Enter, Shift+F3 or Shift+Enter |
| Copy, select all | Ctrl+C, Ctrl+A |
| Zoom in, out, reset | Ctrl++, Ctrl+-, Ctrl+0 |
| Settings | Ctrl+, |
| Close window, quit | Ctrl+W, Ctrl+Q |

Click a footnote marker to see the note. Click elsewhere or press Esc to close it.

In Settings, pick an element on the left, change its properties, and watch the
preview. Apply or OK restyles every open window, in every running mdmd; Cancel discards changes made
since the last Apply. The built-in Default theme cannot be changed, so choosing it
always returns to the original look.

## Where settings are stored

- `~/.config/mdmd/settings.json`: appearance, active theme, window size, recent files
- `~/.config/mdmd/themes/`: one file per saved theme

`$XDG_CONFIG_HOME` is used instead of `~/.config` when it is set. If the settings
file is damaged, mdmd starts with the Default settings and renames the damaged
file to `settings.json.bak` the next time it saves.

## Troubleshooting

**mdmd crashes at start from VS Code's terminal with
`Settings schema 'org.gnome.settings-daemon.plugins.xsettings' does not contain a key named 'antialiasing'`.**
VS Code installed as a snap passes its own GTK and GSettings paths to programs
started in its terminal, and Qt's desktop integration fails with them. Run mdmd
from a regular terminal or the desktop, or clear those variables first:

```bash
env -u GSETTINGS_SCHEMA_DIR -u GTK_PATH -u GTK_EXE_PREFIX -u GIO_MODULE_DIR \
    XDG_DATA_DIRS="$XDG_DATA_DIRS_VSCODE_SNAP_ORIG" uv run mdmd
```

**Diagnostics.** mdmd logs one line per event to stderr (`--verbose` for more).
Logs record counts and kinds of events, never document text, file names, or
settings values.

## Development

```bash
uv sync                      # install, including development tools
uv run pytest                # tests (Qt runs offscreen; no display needed)
uv run pytest --cov          # tests with coverage
uv run ruff check src tests  # lint
uv run ruff format src tests # format
uv run mypy                  # type check (strict)
```

`DESIGN.md` describes the intended behavior. `CLAUDE.md` describes how the code is organized.

## License

MIT. See `LICENSE.md`.
