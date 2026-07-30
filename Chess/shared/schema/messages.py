from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Optional, List, Any


# ── Protocol version ──────────────────────────────────────────────────────────
PROTOCOL_MAJOR = 1
PROTOCOL_MINOR = 0


class NetworkMsgType:
    LOGIN = "login"
    OK = "ok"
    ERROR = "error"
    WAITING = "waiting"
    MATCHED = "matched"
    SNAPSHOT = "snapshot"
    CLICK = "click"
    JUMP = "jump"
    DISCONNECTED = "disconnected"
    RECONNECTED = "reconnected"
    FORFEIT = "forfeit"
    LEADERBOARD = "leaderboard"
    GAME_OVER = "game_over"
    MENU_CHOICE = "menu_choice"
    # wire frame types
    KEYFRAME = "keyframe"
    DELTA = "delta"
    TERMINAL = "terminal"
    REJECTION = "rejection"


# ── Envelope (wraps every message on the wire) ────────────────────────────────

@dataclass
class Envelope:
    """Language-neutral wire envelope. All fields are present on every message."""
    game_id:    str
    session_id: str
    seq:        int
    client_ts:  int   # ms since epoch, set by sender
    server_ts:  int   # ms since epoch, stamped at authoritative node
    payload:    Any   # the inner frame/command dict


# ── Frame types ───────────────────────────────────────────────────────────────

@dataclass
class KeyFrame:
    """Full authoritative board state — used for recovery and reconnect."""
    type:        str = NetworkMsgType.KEYFRAME
    game_id:     str = ""
    server_ts:   int = 0
    node_id:     str = ""          # set by game node; edges repoint caches on receipt
    board:       List[List[str]] = field(default_factory=list)
    active_moves: List[dict]     = field(default_factory=list)
    cooldowns:   List[dict]      = field(default_factory=list)
    game_over:   bool            = False
    winner:      Optional[str]   = None


@dataclass
class DeltaFrame:
    """Minimal delta — only changed squares and updated motion state."""
    type:        str = NetworkMsgType.DELTA
    game_id:     str = ""
    server_ts:   int = 0
    seq:         int = 0
    changes:     List[dict] = field(default_factory=list)   # [{row, col, piece}]
    active_moves: List[dict] = field(default_factory=list)


@dataclass
class TerminalEvent:
    """Emitted once when a game ends."""
    type:       str = NetworkMsgType.TERMINAL
    game_id:    str = ""
    server_ts:  int = 0
    winner:     Optional[str] = None
    reason:     str = ""


@dataclass
class RejectionFrame:
    """Returned to the sender when a command is rejected by the authoritative node."""
    type:       str = NetworkMsgType.REJECTION
    game_id:    str = ""
    server_ts:  int = 0
    seq:        int = 0
    reason:     str = ""


# ── Client → Server messages ──────────────────────────────────────────────────

@dataclass
class LoginMsg:
    name: str
    password: str
    proto_major: int = PROTOCOL_MAJOR
    proto_minor: int = PROTOCOL_MINOR
    type: str = NetworkMsgType.LOGIN


@dataclass
class MenuChoiceMsg:
    choice: str
    room_id: Optional[str] = None
    type: str = NetworkMsgType.MENU_CHOICE


@dataclass
class ClickMsg:
    row: int
    col: int
    type: str = NetworkMsgType.CLICK


@dataclass
class JumpMsg:
    row: int
    col: int
    type: str = NetworkMsgType.JUMP


# ── Server → Client messages ──────────────────────────────────────────────────

@dataclass
class OkMsg:
    range: int
    proto_major: int = PROTOCOL_MAJOR
    proto_minor: int = PROTOCOL_MINOR
    type: str = NetworkMsgType.OK


@dataclass
class ErrorMsg:
    reason: str
    type: str = NetworkMsgType.ERROR


@dataclass
class WaitingMsg:
    type: str = NetworkMsgType.WAITING


@dataclass
class MatchedMsg:
    color: str
    opponent: str
    opponent_range: int
    type: str = NetworkMsgType.MATCHED


@dataclass
class SnapshotMsg:
    clock: int
    board: List[List[str]]
    board_width: int
    board_height: int
    active_moves: List[dict]
    cooldowns: List[dict]
    game_over: bool
    winner: Optional[str] = None
    white_score: int = 0
    black_score: int = 0
    type: str = NetworkMsgType.SNAPSHOT


@dataclass
class DisconnectedMsg:
    player: str
    seconds_remaining: int
    type: str = NetworkMsgType.DISCONNECTED


@dataclass
class ReconnectedMsg:
    player: str
    type: str = NetworkMsgType.RECONNECTED


@dataclass
class ForfeitMsg:
    winner: str
    reason: str
    type: str = NetworkMsgType.FORFEIT


@dataclass
class LeaderboardMsg:
    entries: List[dict]
    type: str = NetworkMsgType.LEADERBOARD


@dataclass
class GameOverMsg:
    winner: str
    new_elo: int
    type: str = NetworkMsgType.GAME_OVER


def to_dict(msg) -> dict:
    if hasattr(msg, "__dataclass_fields__"):
        return asdict(msg)
    return msg
