import json
from typing import Any
from .messages import to_dict, Envelope, PROTOCOL_MAJOR, PROTOCOL_MINOR


def encode(msg: Any) -> str:
    return json.dumps(to_dict(msg))


def decode(raw: str | bytes) -> dict:
    if isinstance(raw, bytes):
        raw = raw.decode()
    return json.loads(raw)


def decode_client_msg(raw: str | bytes) -> dict:
    return decode(raw)


def wrap_envelope(game_id: str, session_id: str, seq: int,
                  client_ts: int, server_ts: int, payload: Any) -> str:
    """Wrap a payload in a wire envelope and encode to JSON."""
    env = Envelope(
        game_id=game_id,
        session_id=session_id,
        seq=seq,
        client_ts=client_ts,
        server_ts=server_ts,
        payload=to_dict(payload) if hasattr(payload, "__dataclass_fields__") else payload,
    )
    return encode(env)


def unwrap_envelope(raw: str | bytes) -> tuple[dict, Any]:
    """Decode a wire envelope. Returns (envelope_fields_dict, payload)."""
    data = decode(raw)
    payload = data.pop("payload", {})
    return data, payload


def check_version(msg: dict) -> bool:
    """Return True if the client protocol major version matches ours."""
    return msg.get("proto_major", PROTOCOL_MAJOR) == PROTOCOL_MAJOR
