"""Edge gateway WebSocket entrypoint.

This file is a migration copy of the current WebSocket server so the gateway
service can exist independently from the API gateway implementation.
"""

import asyncio
import logging
import websockets
from typing import Callable

from shared.events import (
    EventBus,
    InMemoryEventBus,
    COMMAND_SUBJECT,
    MATCH_EVENT_SUBJECT,
    ROOM_EVENT_SUBJECT,
)
from services.auth import authenticate, init_db, get_leaderboard
from services.allocator import allocate_game_node
from services.game_node import run_game, handle_reconnect
from services.matchmaker import run_matchmaker
from services.room_manager import run_room_manager
from shared.protocol import encode, decode, ErrorMsg, OkMsg, WaitingMsg, LeaderboardMsg
from Core.model.config import MsgType

_event_bus: EventBus | None = None

def set_event_bus(event_bus: EventBus) -> None:
    global _event_bus
    _event_bus = event_bus


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = InMemoryEventBus()
        run_matchmaker(_event_bus)
        run_room_manager(_event_bus)
    return _event_bus


async def _wait_for_event(
    subject: str,
    matcher: Callable[[dict], bool],
    timeout: float = 30.0,
) -> dict:
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def _handle_event(message: dict) -> None:
        try:
            if matcher(message) and not future.done():
                future.set_result(message)
        except Exception as exc:  # pragma: no cover
            if not future.done():
                future.set_exception(exc)

    token = get_event_bus().subscribe(subject, _handle_event)
    try:
        return await asyncio.wait_for(future, timeout)
    finally:
        get_event_bus().unsubscribe(token)


logger = logging.getLogger(__name__)

HOST = "0.0.0.0"
PORT = 5555

DEFAULT_PORT_RETRY_COUNT = 5


def build_candidate_ports(port: int, retries: int = DEFAULT_PORT_RETRY_COUNT) -> list[int]:
    """Return a list of ports to attempt if the default port is already in use."""
    return [port + offset for offset in range(retries)]

_LEGACY_CHOICE_MAP = {
    1: "leaderboard", "1": "leaderboard", "leaderboard": "leaderboard",
    2: "match",       "2": "match",       "match":       "match",
    3: "create_room", "3": "create_room", "create_room": "create_room",
    4: "join_room",   "4": "join_room",   "join_room":   "join_room",
    0: "back",        "0": "back",        "back":        "back",
}


def _translate_legacy_choice(choice) -> str:
    return _LEGACY_CHOICE_MAP.get(choice, choice)


def _leaderboard_entries() -> list:
    return [{"name": n, "range": r} for n, r in get_leaderboard(10)]


async def _handle_leaderboard(ws, user, menu_msg) -> None:
    await ws.send(encode(LeaderboardMsg(entries=_leaderboard_entries())))


async def _handle_match(ws, user, menu_msg) -> None:
    done_future = await handle_reconnect(user.name, ws)
    if done_future is not None:
        await done_future
        return

    await ws.send(encode(WaitingMsg()))
    get_event_bus().publish(COMMAND_SUBJECT, {
        "type": "match_request",
        "user": user,
        "ws_ref": ws,
    })

    try:
        match_event = await _wait_for_event(
            MATCH_EVENT_SUBJECT,
            lambda event: event.get("white_ws") is ws or event.get("black_ws") is ws,
            timeout=300.0,
        )
    except asyncio.TimeoutError:
        return

    if match_event.get("white_ws") is ws:
        # White drives run_game — this awaits until the game fully ends
        white_user = match_event["white_user"]
        white_conn = match_event["white_ws"]
        black_user = match_event["black_user"]
        black_conn = match_event["black_ws"]
        allocate_game_node(f"{white_user.name}-{black_user.name}")
        await run_game(white_user, white_conn, black_user, black_conn)
    else:
        # Black: run_game manages this ws directly via player_lifecycle.
        # We must NOT consume messages here — just wait until the connection closes.
        game_done = asyncio.Event()
        async def _wait_close():
            try:
                await ws.wait_closed()
            except Exception:
                pass
            game_done.set()
        asyncio.ensure_future(_wait_close())
        await game_done.wait()


async def _handle_create_room(ws, user, menu_msg) -> None:
    room_password = menu_msg.get("password", "")
    get_event_bus().publish(COMMAND_SUBJECT, {
        "type": "create_room",
        "password": room_password,
        "ws_ref": ws,
        "user": user,
    })

    try:
        room_created = await _wait_for_event(
            ROOM_EVENT_SUBJECT,
            lambda event: event.get("action") == "room_created" and event.get("ws_ref") is ws,
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        await ws.send(encode(ErrorMsg(reason="failed to create room")))
        return

    room_id = room_created["room_id"]
    allocated_node = allocate_game_node(room_id)

    await ws.send(encode({
        "type": MsgType.OK,
        "room_id": room_id,
        "game_node": allocated_node,
        "message": "Room created, waiting for player...",
    }))

    try:
        room_ready = await _wait_for_event(
            ROOM_EVENT_SUBJECT,
            lambda event: event.get("action") == "room_ready" and event.get("room_id") == room_id,
            timeout=300.0,
        )
    except asyncio.TimeoutError:
        get_event_bus().publish(COMMAND_SUBJECT, {
            "type": "leave_room",
            "ws_ref": ws,
        })
        return

    white_user = room_ready["white_user"]
    white_conn = room_ready["white_ws"]
    black_user = room_ready["black_user"]
    black_conn = room_ready["black_ws"]
    viewer_wss = room_ready.get("viewers", [])

    await run_game(white_user, white_conn, black_user, black_conn,
                   viewer_wss=viewer_wss)


async def _handle_join_room(ws, user, menu_msg) -> None:
    room_id = menu_msg.get("room_id")
    room_password = menu_msg.get("password", "")

    get_event_bus().publish(COMMAND_SUBJECT, {
        "type": "join_room",
        "room_id": room_id,
        "password": room_password,
        "ws_ref": ws,
        "user": user,
    })

    try:
        join_result = await _wait_for_event(
            ROOM_EVENT_SUBJECT,
            lambda event: event.get("action") == "room_joined" and event.get("ws_ref") is ws,
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        await ws.send(encode(ErrorMsg(reason="failed to join room")))
        return

    role = join_result.get("role")
    message = join_result.get("message", "")
    if not role:
        await ws.send(encode(ErrorMsg(reason=message)))
        return

    await ws.send(encode({
        "type": MsgType.OK,
        "room_id": room_id,
        "role": role,
        "message": message,
    }))

    # Do NOT consume messages here — run_game's _read_loop needs them.
    # Just wait until the ws closes (game ended or client disconnected).
    game_done = asyncio.Event()
    async def _wait_close():
        try:
            await ws.wait_closed()
        except Exception:
            pass
        game_done.set()
    asyncio.ensure_future(_wait_close())
    await game_done.wait()


_MENU_HANDLERS = {
    "leaderboard": _handle_leaderboard,
    "match":       _handle_match,
    "create_room": _handle_create_room,
    "join_room":   _handle_join_room,
    "back":        None,
}


async def _handle_client(ws_conn) -> None:
    try:
        raw = await ws_conn.recv()
        msg = decode(raw)

        if msg.get("type") != MsgType.LOGIN:
            await ws_conn.send(encode(ErrorMsg(reason="expected login")))
            return

        try:
            user = authenticate(msg.get("name", ""), msg.get("password", ""))
        except ValueError as auth_err:
            await ws_conn.send(encode(ErrorMsg(reason=str(auth_err))))
            return

        await ws_conn.send(encode(OkMsg(range=user.range)))
        await ws_conn.send(encode(LeaderboardMsg(entries=_leaderboard_entries())))

        while True:
            menu_raw = await ws_conn.recv()
            menu_msg = decode(menu_raw)
            raw_choice = menu_msg.get("choice") or menu_msg.get("selection")
            choice = _translate_legacy_choice(raw_choice)

            handler = _MENU_HANDLERS.get(choice)
            if handler is not None:
                await handler(ws_conn, user, menu_msg)

    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception:
        logger.exception("Unhandled error in client handler")
    finally:
        get_event_bus().publish(COMMAND_SUBJECT, {
            "type": "unmatch_request",
            "ws_ref": ws_conn,
        })
        get_event_bus().publish(COMMAND_SUBJECT, {
            "type": "leave_room",
            "ws_ref": ws_conn,
        })


async def main() -> None:
    init_db()
    last_exc = None

    for port in build_candidate_ports(PORT):
        try:
            async with websockets.serve(_handle_client, HOST, port):
                print(f"[server] listening on ws://{HOST}:{port}")
                await asyncio.Future()
        except OSError as exc:
            if exc.errno != 10048:
                raise
            last_exc = exc
            print(f"[server] port {port} is busy, trying {port + 1}...")

    if last_exc is not None:
        print(f"[server] failed to start: {last_exc}")
        raise last_exc


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
