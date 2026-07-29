"""
server.py — WebSocket entry point.

Login flow:
  1. Client sends LoginMsg.
  2. Server authenticates and responds OkMsg.
  3. Client sends menu choice messages in a loop.
"""

import os
import sys
import asyncio
import logging
import websockets

def build_candidate_ports(start_port: int = 5555, max_attempts: int = 10) -> list:
    return [start_port + offset for offset in range(max_attempts)]

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.server.db.db import authenticate, init_db, get_leaderboard
from application.server.matchmaker import Matchmaker
from application.server.room_manager import RoomManager
from application.server.game_server import run_game, handle_reconnect
from application.server.protocol import encode, decode, ErrorMsg, OkMsg, WaitingMsg, LeaderboardMsg
from Core.model.config import MsgType

logger = logging.getLogger(__name__)

HOST = "0.0.0.0"
PORT = 5555

matchmaker = Matchmaker()
room_manager = RoomManager()

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
    matchmaker.register(user, ws)

    result = None
    while result is None:
        try:
            done, pending = await asyncio.wait(
                {asyncio.ensure_future(ws.recv())}, timeout=0.1
            )
            for task in pending:
                task.cancel()
            if done:
                sub_msg = decode(list(done)[0].result())
                if _translate_legacy_choice(sub_msg.get("choice")) == "back":
                    matchmaker.unregister(ws)
                    return
        except Exception:
            pass

        result = await asyncio.get_event_loop().run_in_executor(
            None, matchmaker.poll, ws
        )
        if result is None:
            await asyncio.sleep(0.5)

    if result is False:
        return

    user_a, ws_a, user_b, ws_b = result
    if user_a.range >= user_b.range:
        white_user, white_conn = user_a, ws_a
        black_user, black_conn = user_b, ws_b
    else:
        white_user, white_conn = user_b, ws_b
        black_user, black_conn = user_a, ws_a

    await run_game(white_user, white_conn, black_user, black_conn)


async def _handle_create_room(ws, user, menu_msg) -> None:
    room_password = menu_msg.get("password", "")
    room_id = room_manager.create_room(room_password, ws)
    room = room_manager._rooms.get(room_id)
    room.users[ws] = user

    await ws.send(encode({
        "type": MsgType.OK,
        "room_id": room_id,
        "message": "Room created, waiting for player...",
    }))

    try:
        await asyncio.wait_for(room.ready.wait(), timeout=300)
    except asyncio.TimeoutError:
        room_manager.remove_player(ws)
        return

    room = room_manager._rooms.get(room_id)
    if room and len(room.players) == 2:
        p1_conn, p2_conn = room.players[0], room.players[1]
        user1, user2 = room.users.get(p1_conn), room.users.get(p2_conn)
        if user1 and user2:
            if user1.range >= user2.range:
                white_user, white_conn = user1, p1_conn
                black_user, black_conn = user2, p2_conn
            else:
                white_user, white_conn = user2, p2_conn
                black_user, black_conn = user1, p1_conn
            await run_game(white_user, white_conn, black_user, black_conn,
                           viewer_wss=list(room.viewers))


async def _handle_join_room(ws, user, menu_msg) -> None:
    room_id = menu_msg.get("room_id")
    room_password = menu_msg.get("password", "")

    role, message = room_manager.join_room(room_id, room_password, ws)
    if not role:
        await ws.send(encode(ErrorMsg(reason=message)))
        return

    room = room_manager._rooms.get(room_id)
    if room is None:
        return
    room.users[ws] = user
    await ws.send(encode({
        "type": MsgType.OK,
        "room_id": room_id,
        "role": role,
        "message": message,
    }))

    if len(room.players) == 2:
        room.ready.set()


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
        matchmaker.unregister(ws_conn)
        room_manager.remove_player(ws_conn)


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
