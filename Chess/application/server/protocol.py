# """
# protocol.py — typed WebSocket messages with serialization.

# Client  -> Server:  LoginMsg, ClickMsg, JumpMsg
# Server  -> Client:  OkMsg, ErrorMsg, WaitingMsg, MatchedMsg, SnapshotMsg
# """

# import json
# from dataclasses import dataclass, asdict
# from typing import Optional
# from Core.model.config import MsgType


# # ── client -> server ──────────────────────────────────────────────────────────

# @dataclass
# class LoginMsg:
#     name: str
#     password: str
#     type: str = MsgType.LOGIN

#     def to_dict(self) -> dict:
#         return asdict(self)


# @dataclass
# class ClickMsg:
#     row: int
#     col: int
#     type: str = MsgType.CLICK

#     def to_dict(self) -> dict:
#         return asdict(self)


# @dataclass
# class JumpMsg:
#     row: int
#     col: int
#     type: str = MsgType.JUMP

#     def to_dict(self) -> dict:
#         return asdict(self)


# @dataclass
# class OkMsg:
#     range: int
#     type: str = MsgType.OK

#     def to_dict(self) -> dict:
#         return asdict(self)


# @dataclass
# class ErrorMsg:
#     reason: str
#     type: str = MsgType.ERROR

#     def to_dict(self) -> dict:
#         return asdict(self)


# @dataclass
# class WaitingMsg:
#     type: str = MsgType.WAITING

#     def to_dict(self) -> dict:
#         return asdict(self)


# @dataclass
# class MatchedMsg:
#     color: str
#     opponent: str
#     opponent_range: int
#     type: str = MsgType.MATCHED

#     def to_dict(self) -> dict:
#         return asdict(self)


# @dataclass
# class SnapshotMsg:
#     clock: int
#     board: list
#     board_width: int
#     board_height: int
#     active_moves: list
#     cooldowns: list
#     game_over: bool
#     winner: Optional[str] = None
#     white_score: int = 0
#     black_score: int = 0
#     type: str = MsgType.SNAPSHOT

#     def to_dict(self) -> dict:
#         return asdict(self)


# @dataclass
# class DisconnectedMsg:
#     player: str
#     seconds_remaining: int
#     type: str = MsgType.DISCONNECTED

#     def to_dict(self) -> dict:
#         return asdict(self)


# @dataclass
# class ReconnectedMsg:
#     player: str
#     type: str = MsgType.RECONNECTED

#     def to_dict(self) -> dict:
#         return asdict(self)


# @dataclass
# class ForfeitMsg:
#     winner: str
#     reason: str
#     type: str = MsgType.FORFEIT

#     def to_dict(self) -> dict:
#         return asdict(self)


# @dataclass
# class GameOverMsg:
#     winner: str
#     new_elo: int
#     type: str = MsgType.GAME_OVER

#     def to_dict(self) -> dict:
#         return asdict(self)


# @dataclass
# class LeaderboardMsg:
#     entries: list   # list of {name, range}
#     type: str = MsgType.LEADERBOARD

#     def to_dict(self) -> dict:
#         return asdict(self)


# # ── transport ─────────────────────────────────────────────────────────────────

# def encode(msg) -> str:
#     """Serialize a message dataclass or plain dict to a JSON string."""
#     if hasattr(msg, "to_dict"):
#         return json.dumps(msg.to_dict())
#     return json.dumps(msg)


# def decode(raw) -> dict:
#     """Deserialize a JSON string or bytes to a dict."""
#     if isinstance(raw, bytes):
#         raw = raw.decode()
#     return json.loads(raw)


# def decode_client_msg(raw) -> LoginMsg | ClickMsg | JumpMsg:
#     """Deserialize an incoming client message into the appropriate dataclass."""
#     data = decode(raw)
#     t = data.get("type")
#     if t == MsgType.LOGIN:
#         return LoginMsg(name=data["name"], password=data["password"])
#     if t == MsgType.CLICK:
#         return ClickMsg(row=data["row"], col=data["col"])
#     if t == MsgType.JUMP:
#         return JumpMsg(row=data["row"], col=data["col"])
#     raise ValueError(f"Unknown message type: {t}")


"""
protocol.py — typed WebSocket messages with serialization.

Client  -> Server:  LoginMsg, MenuChoiceMsg, ClickMsg, JumpMsg
Server  -> Client:  OkMsg, ErrorMsg, WaitingMsg, MatchedMsg, SnapshotMsg, LeaderboardMsg
"""

import json
from dataclasses import dataclass, asdict
from typing import Optional

# שכבת האפליקציה מגדירה את סוגי ההודעות בצורה עצמאית
class NetworkMsgType:
    LOGIN         = "login"
    OK            = "ok"
    ERROR         = "error"
    WAITING       = "waiting"
    MATCHED       = "matched"
    SNAPSHOT      = "snapshot"
    CLICK         = "click"
    JUMP          = "jump"
    DISCONNECTED  = "disconnected"
    RECONNECTED   = "reconnected"
    FORFEIT       = "forfeit"
    LEADERBOARD   = "leaderboard"
    GAME_OVER     = "game_over"
    MENU_CHOICE   = "menu_choice"


# ── client -> server ──────────────────────────────────────────────────────────

@dataclass
class LoginMsg:
    name: str
    password: str
    type: str = NetworkMsgType.LOGIN

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MenuChoiceMsg:
    choice: str  # "leaderboard", "match", "join_room", "back"
    room_id: Optional[str] = None
    type: str = NetworkMsgType.MENU_CHOICE

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ClickMsg:
    row: int
    col: int
    type: str = NetworkMsgType.CLICK

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class JumpMsg:
    row: int
    col: int
    type: str = NetworkMsgType.JUMP

    def to_dict(self) -> dict:
        return asdict(self)


# ── server -> client ──────────────────────────────────────────────────────────

@dataclass
class OkMsg:
    range: int
    type: str = NetworkMsgType.OK

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ErrorMsg:
    reason: str
    type: str = NetworkMsgType.ERROR

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WaitingMsg:
    type: str = NetworkMsgType.WAITING

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MatchedMsg:
    color: str
    opponent: str
    opponent_range: int
    type: str = NetworkMsgType.MATCHED

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
    white_score: int = 0
    black_score: int = 0
    type: str = NetworkMsgType.SNAPSHOT

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DisconnectedMsg:
    player: str
    seconds_remaining: int
    type: str = NetworkMsgType.DISCONNECTED

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReconnectedMsg:
    player: str
    type: str = NetworkMsgType.RECONNECTED

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ForfeitMsg:
    winner: str
    reason: str
    type: str = NetworkMsgType.FORFEIT

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GameOverMsg:
    winner: str
    new_elo: int
    type: str = NetworkMsgType.GAME_OVER

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LeaderboardMsg:
    entries: list   # list of {name, range}
    type: str = NetworkMsgType.LEADERBOARD

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


def decode_client_msg(raw) -> LoginMsg | MenuChoiceMsg | ClickMsg | JumpMsg:
    data = decode(raw)
    t = data.get("type")
    if t == NetworkMsgType.LOGIN:
        return LoginMsg(name=data["name"], password=data["password"])
    if t == NetworkMsgType.MENU_CHOICE:
        return MenuChoiceMsg(choice=data.get("choice"), room_id=data.get("room_id"))
    if t == NetworkMsgType.CLICK:
        return ClickMsg(row=data["row"], col=data["col"])
    if t == NetworkMsgType.JUMP:
        return JumpMsg(row=data["row"], col=data["col"])
    raise ValueError(f"Unknown message type: {t}")