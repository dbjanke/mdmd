"""Where mdmd keeps its files, following the XDG base directory convention."""

import os
from pathlib import Path

APP_DIR_NAME = "mdmd"


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    # The XDG spec says a relative value must be ignored.
    root = Path(base) if base and Path(base).is_absolute() else Path.home() / ".config"
    return root / APP_DIR_NAME
