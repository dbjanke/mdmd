"""Reading and atomically writing JSON files."""

import json
import os
import tempfile
from pathlib import Path


def read_json(path: Path) -> object:
    """Raises OSError if unreadable and ValueError if not valid UTF-8 JSON."""
    return json.loads(path.read_bytes().decode("utf-8"))


def write_json_atomic(path: Path, data: object) -> None:
    """Write via a temporary file and rename, so a crash never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        Path(temp_name).replace(path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise
