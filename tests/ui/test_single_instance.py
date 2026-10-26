import uuid
from collections.abc import Callable, Iterator

import pytest
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from mdmd.core.instance_message import MAX_MESSAGE_BYTES
from mdmd.ui.single_instance import InstanceServer, send_to_running_instance


def unique_name() -> str:
    return f"mdmd-test-{uuid.uuid4().hex}"


@pytest.fixture
def make_server(qapp: QApplication) -> Iterator[Callable[[str], InstanceServer]]:
    """Servers live until the test's pending Qt events have run, as they do in the app."""
    servers: list[InstanceServer] = []

    def make(name: str) -> InstanceServer:
        server = InstanceServer(name)
        servers.append(server)
        return server

    yield make
    QApplication.processEvents()
    for server in servers:
        server.close()


def test_no_running_instance(qtbot: QtBot) -> None:
    assert not send_to_running_instance(["/a.md"], name=unique_name())


def test_paths_reach_the_running_instance(qtbot: QtBot, make_server: Callable[[str], InstanceServer]) -> None:
    name = unique_name()
    server = make_server(name)
    assert server.start()
    with qtbot.waitSignal(server.open_requested, timeout=3000) as signal:
        assert send_to_running_instance(["/a.md", "/b c.md"], name=name)
    assert signal.args == [["/a.md", "/b c.md"]]


def test_empty_request_means_launcher(qtbot: QtBot, make_server: Callable[[str], InstanceServer]) -> None:
    name = unique_name()
    server = make_server(name)
    assert server.start()
    with qtbot.waitSignal(server.open_requested, timeout=3000) as signal:
        send_to_running_instance([], name=name)
    assert signal.args == [[]]


def test_stale_socket_is_replaced(qtbot: QtBot, make_server: Callable[[str], InstanceServer]) -> None:
    name = unique_name()
    stale = QLocalServer()
    assert stale.listen(name)
    stale.close()  # leaves nothing listening, as after a crash
    server = make_server(name)
    assert server.start()


def _send_raw(name: str, data: bytes) -> None:
    socket = QLocalSocket()
    socket.connectToServer(name)
    assert socket.waitForConnected(1000)
    socket.write(data)
    socket.flush()
    socket.waitForBytesWritten(1000)
    socket.disconnectFromServer()


@pytest.mark.parametrize("data", [b"not json", b'{"version": 1, "open": ["relative.md"]}', b""])
def test_bad_messages_are_ignored_and_the_server_keeps_working(
    qtbot: QtBot, make_server: Callable[[str], InstanceServer], data: bytes
) -> None:
    name = unique_name()
    server = make_server(name)
    assert server.start()
    with qtbot.assertNotEmitted(server.open_requested, wait=200):
        _send_raw(name, data)
    with qtbot.waitSignal(server.open_requested, timeout=3000):
        send_to_running_instance(["/ok.md"], name=name)


def test_oversized_message_is_dropped(qtbot: QtBot, make_server: Callable[[str], InstanceServer]) -> None:
    name = unique_name()
    server = make_server(name)
    assert server.start()
    with qtbot.assertNotEmitted(server.open_requested, wait=300):
        _send_raw(name, b"x" * (MAX_MESSAGE_BYTES + 10))
