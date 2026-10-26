"""The message a second mdmd launch sends to the running instance: which files to open."""

import json

MESSAGE_VERSION = 1
MAX_MESSAGE_BYTES = 1_000_000


class InstanceMessageError(ValueError):
    pass


def encode_open_request(paths: list[str]) -> bytes:
    """`paths` must be absolute, since the running instance has its own working directory."""
    return json.dumps({"version": MESSAGE_VERSION, "open": paths}).encode("utf-8")


def decode_open_request(data: bytes) -> list[str]:
    if len(data) > MAX_MESSAGE_BYTES:
        raise InstanceMessageError("message too large")
    try:
        message = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InstanceMessageError("message is not valid JSON") from error
    if not isinstance(message, dict) or message.get("version") != MESSAGE_VERSION:
        raise InstanceMessageError("unsupported message version")
    paths = message.get("open")
    if not isinstance(paths, list) or not all(isinstance(p, str) and p.startswith("/") for p in paths):
        raise InstanceMessageError("'open' must be a list of absolute paths")
    return paths
