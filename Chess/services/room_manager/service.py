from __future__ import annotations

from shared.events import (
    EventBus,
    InMemoryEventBus,
    COMMAND_SUBJECT,
    ROOM_EVENT_SUBJECT,
)
from services.room_manager import RoomManager

_event_bus: EventBus | None = None
_room_manager: RoomManager | None = None


def _handle_command(command: dict) -> None:
    if _room_manager is None:
        return

    action = command.get("type")
    if action == "create_room":
        password = command.get("password", "")
        ws_ref = command.get("ws_ref")
        user = command.get("user")
        if ws_ref is not None and user is not None:
            room_id = _room_manager.create_room(password, ws_ref)
            room = _room_manager._rooms.get(room_id)
            if room is not None:
                room.users[ws_ref] = user
            _event_bus.publish(ROOM_EVENT_SUBJECT, {
                "action": "room_created",
                "room_id": room_id,
                "ws_ref": ws_ref,
                "user": user,
            })

    elif action == "join_room":
        room_id = command.get("room_id")
        password = command.get("password", "")
        ws_ref = command.get("ws_ref")
        user = command.get("user")
        if room_id is not None and ws_ref is not None and user is not None:
            role, message = _room_manager.join_room(room_id, password, ws_ref)
            room = _room_manager._rooms.get(room_id)
            if room is not None:
                room.users[ws_ref] = user
            event = {
                "action": "room_joined",
                "room_id": room_id,
                "ws_ref": ws_ref,
                "role": role,
                "message": message,
                "user": user,
            }
            _event_bus.publish(ROOM_EVENT_SUBJECT, event)

            if role == "player" and room is not None and len(room.players) == 2:
                first, second = room.players[0], room.players[1]
                first_user = room.users.get(first)
                second_user = room.users.get(second)
                if first_user is not None and second_user is not None:
                    range_f = first_user["range"]  if isinstance(first_user,  dict) else first_user.range
                    range_s = second_user["range"] if isinstance(second_user, dict) else second_user.range
                    if range_f >= range_s:
                        white_conn, black_conn = first, second
                        white_user, black_user = first_user, second_user
                    else:
                        white_conn, black_conn = second, first
                        white_user, black_user = second_user, first_user
                    room.ready.set()
                    _event_bus.publish(ROOM_EVENT_SUBJECT, {
                        "action": "room_ready",
                        "room_id": room_id,
                        "white_user": white_user,
                        "white_ws": white_conn,
                        "black_user": black_user,
                        "black_ws": black_conn,
                        "viewers": list(room.viewers),
                    })

    elif action == "leave_room":
        ws_ref = command.get("ws_ref")
        if ws_ref is not None:
            deleted_room = _room_manager.remove_player(ws_ref)
            _event_bus.publish(ROOM_EVENT_SUBJECT, {
                "action": "room_left",
                "room_id": deleted_room,
                "ws_ref": ws_ref,
            })


def run_room_manager(event_bus: EventBus | None = None) -> EventBus:
    global _event_bus, _room_manager
    if event_bus is None:
        event_bus = InMemoryEventBus()

    _event_bus = event_bus
    _room_manager = RoomManager()
    event_bus.subscribe(COMMAND_SUBJECT, _handle_command)
    return event_bus
