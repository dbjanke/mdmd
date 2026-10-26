"""Command-line entry point: `mdmd [FILE ...]`."""

import argparse
import logging
import os
import sys
from pathlib import Path
from types import TracebackType

from PySide6.QtWidgets import QApplication

from mdmd.logs import configure_logging, get_logger, log_event
from mdmd.storage.config_paths import config_dir
from mdmd.storage.settings_store import SettingsStore
from mdmd.storage.theme_store import ThemeStore
from mdmd.ui.application import Application
from mdmd.ui.fonts import FontResolver
from mdmd.ui.prompts import QtPrompts
from mdmd.ui.single_instance import InstanceServer, send_to_running_instance

_log = get_logger("main")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="mdmd", description="Display Markdown files as formatted, read-only text.")
    parser.add_argument("files", nargs="*", type=Path, help="Markdown files to open, one window each")
    parser.add_argument("--verbose", action="store_true", help="log debug detail to stderr")
    return parser.parse_args(argv)


def _log_unhandled(kind: type[BaseException], error: BaseException, trace: TracebackType | None) -> None:
    log_event(_log, "unhandled_exception", logging.ERROR, error=kind.__name__)
    _log.error("traceback", exc_info=(kind, error, trace))


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    configure_logging(logging.DEBUG if args.verbose else logging.INFO)
    sys.excepthook = _log_unhandled

    existing = QApplication.instance()
    qt_app = existing if isinstance(existing, QApplication) else QApplication(sys.argv[:1])
    qt_app.setApplicationName("mdmd")
    qt_app.setDesktopFileName("mdmd")
    qt_app.setQuitOnLastWindowClosed(False)  # the Application decides; the settings dialog alone does not keep it open

    # abspath normalizes '..' without resolving symlinks, so recent files show the path the user gave.
    paths = [os.path.abspath(path) for path in args.files]  # noqa: PTH100
    if send_to_running_instance(paths):
        log_event(_log, "handed_to_running_instance", count=len(paths))
        return 0

    directory = config_dir()
    app = Application(SettingsStore(directory), ThemeStore(directory), QtPrompts(), FontResolver())
    app.last_window_closed.connect(qt_app.quit)
    server = InstanceServer()
    server.open_requested.connect(app.handle_open_request)
    server.start()
    app.start([Path(p) for p in paths])
    return qt_app.exec()


if __name__ == "__main__":
    sys.exit(main())
