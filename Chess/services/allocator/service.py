"""Allocator service — placement, directory, supervision, room lobbies.

Backed by an in-memory store (swap _store for Redis in production).
"""

import time

# ── In-memory backing store (Redis in production) ─────────────────────────────
_placements: dict[str, dict] = {}   # game_id -> {node_id, lease_expires_at}
_directory:  dict[str, str]  = {}   # game_id -> node_id  (fast lookup)
_rooms:      dict[str, dict] = {}   # room_id -> {state, game_id|None, ...}

_LEASE_TTL_S = 30.0   # node lease duration; supervision detects expiry


# ── Placement ─────────────────────────────────────────────────────────────────

def allocate_game_node(game_id: str) -> str:
    """Assign a game node for game_id. Idempotent — returns existing node if already placed."""
    if game_id in _placements:
        return _placements[game_id]["node_id"]
    node_id = f"game-node-{len(_placements) + 1}"
    _placements[game_id] = {
        "node_id": node_id,
        "lease_expires_at": time.time() + _LEASE_TTL_S,
    }
    _directory[game_id] = node_id
    return node_id


def get_allocated_node(game_id: str) -> str | None:
    """Return the allocated node for a game, or None."""
    return _directory.get(game_id)


def renew_lease(game_id: str) -> bool:
    """Renew the node lease for a game. Returns False if game is not placed."""
    if game_id not in _placements:
        return False
    _placements[game_id]["lease_expires_at"] = time.time() + _LEASE_TTL_S
    return True


# ── Supervision ───────────────────────────────────────────────────────────────

def get_expired_games() -> list[str]:
    """Return game_ids whose node lease has expired (node presumed failed)."""
    now = time.time()
    return [gid for gid, p in _placements.items()
            if p["lease_expires_at"] < now]


def reassign_game(game_id: str) -> str:
    """Reassign a game to a new node after a failure. Returns the new node_id."""
    old = _placements.pop(game_id, None)
    old_node = old["node_id"] if old else "unknown"
    new_node = f"game-node-rebuild-{game_id}"
    _placements[game_id] = {
        "node_id": new_node,
        "lease_expires_at": time.time() + _LEASE_TTL_S,
    }
    _directory[game_id] = new_node
    return new_node


# ── Room lobbies ──────────────────────────────────────────────────────────────
# State machine: waiting → live → ended  (one-way, no promotion of spectators)

def create_lobby(room_id: str) -> dict:
    """Create a room lobby in 'waiting' state. game_id is not exposed until live."""
    _rooms[room_id] = {"state": "waiting", "game_id": None}
    return _rooms[room_id]


def claim_seat(room_id: str) -> tuple[bool, str | None]:
    """
    Atomic seat-2 claim. Returns (True, game_id) on success, (False, None) if
    the room is already live or ended (subsequent joins are spectator-only).
    """
    room = _rooms.get(room_id)
    if room is None or room["state"] != "waiting":
        return False, None
    game_id = f"game-{room_id}"
    room["state"]   = "live"
    room["game_id"] = game_id
    allocate_game_node(game_id)
    return True, game_id


def end_lobby(room_id: str) -> None:
    """Transition a room to 'ended' state."""
    room = _rooms.get(room_id)
    if room:
        room["state"] = "ended"


def get_lobby(room_id: str) -> dict | None:
    return _rooms.get(room_id)


def run_allocator() -> None:
    pass
