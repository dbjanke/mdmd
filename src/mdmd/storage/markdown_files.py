"""Reading a Markdown file from disk."""

from enum import Enum
from pathlib import Path

from mdmd.core.document import Document
from mdmd.core.parser import DocumentParseError, parse_markdown

MAX_FILE_BYTES = 20 * 1024 * 1024  # far beyond any hand-written document; guards against opening e.g. a disk image


class OpenFailure(Enum):
    NOT_FOUND = "does not exist"
    IS_DIRECTORY = "is a folder, not a file"
    UNREADABLE = "cannot be read"
    TOO_LARGE = "is too large to display"
    UNDISPLAYABLE = "could not be displayed"


class FileOpenError(Exception):
    def __init__(self, path: Path, failure: OpenFailure) -> None:
        super().__init__(f"{path} {failure.value}.")
        self.path = path
        self.failure = failure


def read_markdown_file(path: Path) -> str:
    """The file's text. Bytes that are not valid UTF-8 become U+FFFD. Raises FileOpenError."""
    if path.is_dir():
        raise FileOpenError(path, OpenFailure.IS_DIRECTORY)
    try:
        with path.open("rb") as handle:
            data = handle.read(MAX_FILE_BYTES + 1)
    except FileNotFoundError as error:
        raise FileOpenError(path, OpenFailure.NOT_FOUND) from error
    except OSError as error:
        raise FileOpenError(path, OpenFailure.UNREADABLE) from error
    if len(data) > MAX_FILE_BYTES:
        raise FileOpenError(path, OpenFailure.TOO_LARGE)
    return data.decode("utf-8", errors="replace")


def load_document(path: Path) -> Document:
    """Read and parse `path`. Raises FileOpenError for any failure, including content that cannot be displayed."""
    text = read_markdown_file(path)
    try:
        return parse_markdown(text)
    except DocumentParseError as error:
        raise FileOpenError(path, OpenFailure.UNDISPLAYABLE) from error
