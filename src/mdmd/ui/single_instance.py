"""One mdmd per user: later launches hand their files to the running instance over a local socket."""

import logging
import os
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from mdmd.core.instance_message import (
    MAX_MESSAGE_BYTES,
    InstanceMessageError,
    decode_open_request,
    encode_open_request,
)
from mdmd.logs import get_logger, log_event

CONNECT_TIMEOUT_MS = 500
WRITE_TIMEOUT_MS = 2000
SOCKET_NAME = "mdmd.sock"

_log = get_logger("single_instance")


def socket_path() -> str:
    """In the per-user runtime folder when there is one (only this user can reach it)."""
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime and Path(runtime).is_dir():
        return str(Path(runtime) / SOCKET_NAME)
    return f"mdmd-{os.getuid()}"


def send_to_running_instance(paths: list[str], name: str | None = None) -> bool:
    """Ask a running instance to open `paths`. False if there is no running instance."""
    socket = QLocalSocket()
    socket.connectToServer(name or socket_path())
    if not socket.waitForConnected(CONNECT_TIMEOUT_MS):
        return False
    socket.write(encode_open_request(paths))
    socket.flush()
    socket.waitForBytesWritten(WRITE_TIMEOUT_MS)
    socket.disconnectFromServer()
    if socket.state() != QLocalSocket.LocalSocketState.UnconnectedState:
        socket.waitForDisconnected(WRITE_TIMEOUT_MS)
    return True


class InstanceServer(QObject):
    open_requested = Signal(list)  # list[str] of absolute paths; empty means "show a launcher"

    def __init__(self, name: str | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._name = name or socket_path()
        self._server = QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self._server.newConnection.connect(self._accept)
        self._buffers: dict[QLocalSocket, bytearray] = {}

    def start(self) -> bool:
        """Listen for later launches. Call only after `send_to_running_instance` found no instance."""
        if self._server.listen(self._name):
            return True
        # Nobody answered, so a socket left by a crashed instance is in the way.
        QLocalServer.removeServer(self._name)
        if self._server.listen(self._name):
            return True
        log_event(_log, "listen_failed", level=logging.WARNING, error=self._server.errorString())
        return False

    def close(self) -> None:
        self._server.close()

    def _accept(self) -> None:
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            self._buffers[socket] = bytearray()
            socket.readyRead.connect(lambda s=socket: self._read(s))
            socket.disconnected.connect(lambda s=socket: self._finish(s))

    def _read(self, socket: QLocalSocket) -> None:
        buffer = self._buffers.get(socket)
        if buffer is None:
            return
        buffer.extend(bytes(socket.readAll().data()))
        if len(buffer) > MAX_MESSAGE_BYTES:
            log_event(_log, "message_too_large", level=logging.WARNING)
            self._buffers.pop(socket, None)
            socket.abort()

    def _finish(self, socket: QLocalSocket) -> None:
        self._read(socket)
        buffer = self._buffers.pop(socket, None)
        socket.deleteLater()
        if buffer is None:
            return
        try:
            paths = decode_open_request(bytes(buffer))
        except InstanceMessageError as error:
            log_event(_log, "message_rejected", level=logging.WARNING, error=str(error))
            return
        self.open_requested.emit(paths)
