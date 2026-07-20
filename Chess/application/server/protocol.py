"""
protocol.py — typed WebSocket messages with serialization.

Client  -> Server:  LoginMsg, ClickMsg, JumpMsg
Server  -> Client:  OkMsg, ErrorMsg, WaitingMsg, MatchedMsg, SnapshotMsg
"""

import json
from dataclasses import dataclass, asdict
from typing import Optional


# ── client -> server ──────────────────────────────────────────────────────────

@dataclass
class LoginMsg:
    name: str
    password: str
    type: str = "login"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ClickMsg:
    row: int
    col: int
    type: str = "click"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class JumpMsg:
    row: int
    col: int
    type: str = "jump"

    def to_dict(self) -> dict:
        return asdict(self)


# ── server -> client ──────────────────────────────────────────────────────────

@dataclass
class OkMsg:
    range: int
    type: str = "ok"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ErrorMsg:
    reason: str
    type: str = "error"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WaitingMsg:
    type: str = "waiting"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MatchedMsg:
    color: str
    opponent: str
    opponent_range: int
    type: str = "matched"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SnapshotMsg:
    clock: int
    board: list
    board_width: int
    board_height: int
    active_moves: list
    cooldowns: list
    game_over: bool
    winner: Optional[str] = None
    type: str = "snapshot"

    def to_dict(self) -> dict:
        return asdict(self)


# ── transport ─────────────────────────────────────────────────────────────────

def encode(msg) -> str:
    """Serialize a message dataclass or plain dict to a JSON string."""
    if hasattr(msg, "to_dict"):
        return json.dumps(msg.to_dict())
    return json.dumps(msg)


def decode(raw) -> dict:
    """Deserialize a JSON string or bytes to a dict."""
    if isinstance(raw, bytes):
        raw = raw.decode()
    return json.loads(raw)


def decode_client_msg(raw) -> LoginMsg | ClickMsg | JumpMsg:
    """Deserialize an incoming client message into the appropriate dataclass."""
    data = decode(raw)
    t = data.get("type")
    if t == "login":
        return LoginMsg(name=data["name"], password=data["password"])
    if t == "click":
        return ClickMsg(row=data["row"], col=data["col"])
    if t == "jump":
        return JumpMsg(row=data["row"], col=data["col"])
    raise ValueError(f"Unknown message type: {t}")
