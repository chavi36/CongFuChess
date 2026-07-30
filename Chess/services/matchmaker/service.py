from __future__ import annotations

from shared.events import (
    EventBus,
    InMemoryEventBus,
    COMMAND_SUBJECT,
    MATCH_EVENT_SUBJECT,
)
from services.matchmaker import Matchmaker

_event_bus: EventBus | None = None
_matchmaker: Matchmaker | None = None


def _handle_command(command: dict) -> None:
    if _matchmaker is None:
        return

    if command.get("type") == "match_request":
        user = command.get("user")
        ws_ref = command.get("ws_ref")
        if user is not None and ws_ref is not None:
            _matchmaker.register(user, ws_ref)
            # Try to match all waiting players, not just the one who just registered
            for ws in _matchmaker.all_waiting_ws():
                result = _matchmaker.poll(ws)
                if result is not None:
                    break
            else:
                result = None

    elif command.get("type") == "unmatch_request":
        ws_ref = command.get("ws_ref")
        if ws_ref is not None:
            _matchmaker.unregister(ws_ref)
        result = None

    else:
        result = _matchmaker.poll(command.get("ws_ref"))
        result = None  # other commands don't trigger matching

    if result is not None:
        user_a, ws_a, user_b, ws_b = result
        range_a = user_a["range"] if isinstance(user_a, dict) else user_a.range
        range_b = user_b["range"] if isinstance(user_b, dict) else user_b.range
        name_a  = user_a["name"]  if isinstance(user_a, dict) else user_a.name
        name_b  = user_b["name"]  if isinstance(user_b, dict) else user_b.name
        if range_a >= range_b:
            white_user, white_ws, black_user, black_ws = user_a, ws_a, user_b, ws_b
        else:
            white_user, white_ws, black_user, black_ws = user_b, ws_b, user_a, ws_a

        _event_bus.publish(MATCH_EVENT_SUBJECT, {
            "white_user": white_user,
            "white_ws":   white_ws,
            "black_user": black_user,
            "black_ws":   black_ws,
            "game_id":    f"{name_a}-{name_b}",
        })


def run_matchmaker(event_bus: EventBus | None = None) -> EventBus:
    global _event_bus, _matchmaker
    if event_bus is None:
        event_bus = InMemoryEventBus()

    _event_bus = event_bus
    _matchmaker = Matchmaker()
    event_bus.subscribe(COMMAND_SUBJECT, _handle_command)
    return event_bus
