"""Spectator relay service implementation for Kung-Fu Chess.

Read-only: subscribes to player/spectator frames and terminal events.
Caches keyframes at a 10 s cadence for watched games only.
Maintains a short post-game cache after terminal events.
"""

from shared.events import (
    InMemoryEventBus,
    PLAYER_FRAME_SUBJECT,
    SPECTATOR_FRAME_SUBJECT,
    KEYFRAME_SUBJECT,
    TERMINAL_EVENT_SUBJECT,
)

_KEYFRAME_INTERVAL_MS = 10_000   # emit a keyframe every 10 s of game time
_POST_GAME_CACHE_MS   = 30_000   # keep last keyframe for 30 s after game ends

# per-game state: {game_id: {"last_keyframe_ts": int, "last_frame": dict, "ended_at": int|None}}
_game_state: dict[str, dict] = {}
_last_spectator_frame: dict | None = None


def _get_or_create(game_id: str) -> dict:
    if game_id not in _game_state:
        _game_state[game_id] = {"last_keyframe_ts": -_KEYFRAME_INTERVAL_MS, "last_frame": None, "ended_at": None}
    return _game_state[game_id]


def _handle_frame(frame: dict, bus: InMemoryEventBus) -> None:
    global _last_spectator_frame
    game_id = frame.get("game_id")
    if not game_id:
        return

    state = _get_or_create(game_id)
    if state["ended_at"] is not None:
        return  # read-only: drop frames for ended games

    state["last_frame"] = frame.copy()
    _last_spectator_frame = frame.copy()

    game_ts = frame.get("game_time_ms", 0)
    if game_ts - state["last_keyframe_ts"] >= _KEYFRAME_INTERVAL_MS:
        state["last_keyframe_ts"] = game_ts
        bus.publish(KEYFRAME_SUBJECT, {**frame, "frame_type": "keyframe"})


def _handle_terminal(event: dict) -> None:
    game_id = event.get("game_id")
    if not game_id:
        return
    state = _get_or_create(game_id)
    state["ended_at"] = event.get("game_time_ms", 0)


def relay_frame(frame: dict) -> None:
    """Relay frame data to spectator consumers (used in tests/direct calls)."""
    global _last_spectator_frame
    _last_spectator_frame = frame.copy()


def last_frame() -> dict | None:
    return _last_spectator_frame


def get_last_spectator_frame() -> dict | None:
    return _last_spectator_frame


def get_last_keyframe(game_id: str) -> dict | None:
    state = _game_state.get(game_id)
    return state["last_frame"] if state else None


def run_spectator_relay(event_bus: InMemoryEventBus | None = None) -> InMemoryEventBus:
    """Run the spectator relay service process."""
    global _game_state, _last_spectator_frame
    _game_state = {}
    _last_spectator_frame = None

    if event_bus is None:
        event_bus = InMemoryEventBus()

    event_bus.subscribe(PLAYER_FRAME_SUBJECT,    lambda f: _handle_frame(f, event_bus))
    event_bus.subscribe(SPECTATOR_FRAME_SUBJECT, lambda f: _handle_frame(f, event_bus))
    event_bus.subscribe(TERMINAL_EVENT_SUBJECT,  _handle_terminal)
    return event_bus
