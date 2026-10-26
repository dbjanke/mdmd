# CLAUDE.md

Working notes for developing mdmd. Follow `AGENTS.md` for general principles.
`DESIGN.md` is the behavior spec and stays free of implementation detail (another
team could build it in a different stack); architecture notes belong here.
`README.md` is for people who download and use the project.

## Stack

Python 3.12, PySide6 (`pyside6-essentials` only: never add `pyside6` or WebEngine;
the spec forbids a browser engine), markdown-it-py with mdit-py-plugins and
linkify-it-py. Tooling: uv, ruff (lint and format), mypy strict, pytest with
pytest-qt and pytest-cov.

## Commands

```bash
uv run pytest -q             # all tests, offscreen Qt
uv run pytest --cov          # coverage (currently about 97%)
uv run ruff check src tests && uv run ruff format --check src tests
uv run mypy
uv run mdmd FILE.md          # run the app (see the snap note below)
env -u GSETTINGS_SCHEMA_DIR -u GTK_PATH -u GTK_EXE_PREFIX -u GIO_MODULE_DIR XDG_DATA_DIRS="$XDG_DATA_DIRS_VSCODE_SNAP_ORIG" XDG_CONFIG_HOME=/tmp/mdmd-cfg timeout 5 uv run mdmd FILE.md   # smoke-run from the VS Code snap terminal without touching real settings (exit 124 = still running, i.e. OK)
```

## Testing

- Check renderer changes visually: render with `render_document(...)`, set `document.setTextWidth(800)`, call `drawContents` onto a `QImage` under `QT_QPA_PLATFORM=offscreen`, save a PNG to the scratchpad and look at it. Widgets can use `widget.grab().save(...)`.
- Use `FakePrompts` (tests/ui/conftest.py) for every dialog answer. Never let a real `QMessageBox` or file chooser open in tests.
- Tests use public accessors (`find_bar.field`, `dialog.save_theme_button`, …), not `_private` attributes. Add a property when a test needs one. `SLF001` isn't enabled, so ruff strips `# noqa: SLF001` as unused.
- Keep Qt objects that own pending events (sockets, servers, timers) alive until `QApplication.processEvents()` runs at teardown. Freeing them earlier segfaults later, in an unrelated test.
- Two `Application`s on one `config_dir` (the `make_app` fixture called twice) stand in for two mdmd processes. Use `qtbot.waitUntil` for changes that arrive through the file watchers.
- Simulate an unwritable settings or themes folder with `read_only(dir)` plus `@needs_permissions` (tests/ui/conftest.py). A folder in place of `settings.json` is treated as a damaged file and set aside as `.bak`, not as a write failure.
- Check that a race or edge-case test fails with the fix removed before trusting it. The settings-lock test lost updates in 14 of 15 trial runs without the lock.
- Give parametrized hostile-input tests short `ids=`, or pytest prints the whole input.
- If the full suite crashes but each file passes alone, look for a Qt object freed too early (`pytest -v` shows which test was running).

## Layout

The dependency direction is `ui` → `storage` → `core`. `core` never imports Qt or does IO.

- `src/mdmd/core/`: pure logic, tested without Qt
  - `document.py`: the document model (frozen dataclasses: blocks and inlines)
  - `parser.py`: markdown-it tokens → `Document`; footnotes are `NoteRef`s keyed into `Document.notes`
  - `citations.py`: turns `[N]` into `NoteRef`s when the document ends with a Sources-style heading plus an ordered list
  - `style.py`: element/property schema, validation, lenient parsing (`parse_style` falls back per property)
  - `default_style.py`: the Default theme's values (data only)
  - `cascade.py`: inheritance rules (paragraphs in lists/quotes, table font fallback, popup style), additive gaps
  - `themes.py`, `settings_draft.py`: theme naming rules, the library, and the settings dialog's working state
  - `app_settings.py`, `recent.py`, `search.py`, `zoom.py`, `links.py`, `popup_placement.py`: small focused rules
  - `settings_changes.py`: each way the settings change, as a named `SettingsChange` function (`recent_file_opened`, `theme_deleted`, …)
- `src/mdmd/storage/`: files on disk (atomic JSON writes, settings file with `.bak` handling, one file per theme, reading Markdown with a size limit)
- `src/mdmd/ui/`: Qt
  - `renderer.py`: `Document` + `Style` → `QTextDocument` (the hard part; see below)
  - `text_objects.py`: footnote pills drawn as custom text objects
  - `document_view.py`: `QTextBrowser` subclass for marker clicks, heading links, Copy Link Address, plain-text copy, find highlights
  - `document_panel.py`: one document with its find bar, popup, zoom, reload, and file watcher
  - `main_window.py`: launcher or document window, plus menus. `WindowHost` is the narrow interface it needs.
  - `application.py`: owns the windows and decides where files open; reacts to `SharedSettings` signals
  - `shared_settings.py`: `SharedSettings` owns settings and themes, saves changes, watches for changes from other processes, and emits `settings_changed(previous, current)` / `themes_changed`
  - `settings_dialog.py`, `property_editors.py`: the settings UI (`SettingsHost` interface)
  - `prompts.py`: every message box and file chooser goes through `Prompts`, so tests inject `FakePrompts`
  - `file_watcher.py`: debounced change detection for an open document; also used on the settings file and themes folder
- `src/mdmd/ui/untrusted_text.py`: shows file names and document text literally in tooltips and menus; `prompts.plain_message_box` does the same for message boxes.
- `src/mdmd/logs.py`: key=value structured logging. Never log document text, paths, or settings values.

## Renderer facts (verified by experiment; tests pin them)

- Qt merges adjacent block margins by taking the larger one. mdmd's gaps are additive, so each element's whole gap (previous space after + its own space before) is its top margin, and bottom margins are 0.
- Qt ignores the top margin of the first block after a frame (code block, quote, table). That gap goes on the frame's bottom margin instead (`_frame_just_left`).
- Inserting a frame at an empty block leaves that block in place, so empty "fresh" blocks are collapsed to zero height first.
- Qt's horizontal ruler draws from the table's right edge when it directly follows a table. A collapsed spacer block is placed between them. The ruler color is the block's background brush.
- Units: fonts use `setPointSizeF`; margins and fixed line heights use 96-dpi pixels (`PX_PER_PT = 96/72`). Line spacing uses `FixedHeight` (a multiple of the font size), or `MinimumHeight` when the block holds an image.
- Zoom re-renders with scaled sizes. `QTextEdit.zoomIn` would not work, because every format has an explicit size.
- Raw text positions (`toRawText`) map one-to-one onto document positions; find relies on this.

## Gotchas

- Keep a Python reference to every `QTextDocument` (`RenderedDocument`) while anything uses it; a garbage-collected temporary crashes Qt. Tests keep them alive in `_alive`.
- Delayed callbacks must be tied to their widget: `QTimer.singleShot(0, self, fn)`.
- Connecting a Qt signal straight to a PySide `Signal(object)` can fail at runtime; use a lambda.
- Treat file names, paths, link addresses and document text as untrusted. Qt tooltips and message boxes render anything that looks like HTML as HTML, and menus treat `&` as a shortcut marker. Route such text through `ui/untrusted_text.py` or `prompts.plain_message_box`.
- Each launch is its own process (single-instance was removed: its socket was an attack surface). Change settings only via `SharedSettings.change(...)` (raises on failure; use it for user actions like Apply) or `change_quietly(...)` (logs, keeps the change in memory; use it for recent files and window size), passing a change from `core/settings_changes.py`. Both do a locked read-merge-write; never write the settings file directly.
- `FileWatcher` records the new state before it emits `changed`. Call `accept_current()` only after writing or reloading the watched file yourself, so the watcher doesn't report that change back.
- Open documents with `storage.markdown_files.load_document`, which turns every read or parse failure into `FileOpenError`. Never call `parse_markdown` on file content and let its errors escape.
- Recursive walks over inline content stay bounded only because the parser flattens past `MAX_INLINE_DEPTH`. Keep that cap if you change the parser.
- Don't name properties or methods after `QWidget`/`QObject` methods (`find`, `children`, `parent`, `size`, …). mypy strict reports the override; heed it.
- `CLAUDE-SECURITY-<timestamp>/` folders are Claude Security scan reports. Each has its own `.gitignore`; don't edit them or commit them.
- VS Code installed as a snap sets `GSETTINGS_SCHEMA_DIR`, `GTK_PATH`, and `XDG_DATA_DIRS`, which crash Qt (and GTK) at startup in its terminal. Tests are unaffected (offscreen). To run the app from that terminal, see the README's Troubleshooting section.

## Decisions made with the product owner

- Qt chosen over GTK for its text document model: selection, find, and copy work across tables and images.
- Links never open anything. Only same-document `#heading` links act. Tooltips and Copy Link Address expose the target.
- A built-in read-only "Default" theme replaces "Factory" and the Reset button.
- Each user theme is its own file. All other settings share one file.
- Table font is optional (unset means the body font).
- Zoom and automatic reload are included.
- Single-instance was dropped. Each launch is its own process; the same file may be open in two processes, and that's acceptable.
- Nothing in a footnote popup is clickable: inner markers show as plain `[n]` text.
- Reopening a file that's already open brings its window forward and moves it to the top of Recent Files.
