# """
# server.py — WebSocket entry point.

# Login flow:
#   1. Client sends LoginMsg.
#   2. Server authenticates and responds OkMsg.
#   3. If the user has a game waiting for reconnection, they are routed back in.
#   4. Otherwise they are queued in the matchmaker and sent WaitingMsg.
# """

# import asyncio
# import websockets

# from application.server.db.db import authenticate, init_db, get_leaderboard
# from application.server.matchmaker import Matchmaker
# from application.server.game_server import run_game, handle_reconnect
# from application.server.protocol import encode, decode, ErrorMsg, OkMsg, WaitingMsg, LeaderboardMsg
# from Core.model.config import MsgType

# HOST = "0.0.0.0"
# PORT = 5555

# matchmaker = Matchmaker()


# async def _handle_client(ws) -> None:
#     try:
#         raw = await ws.recv()
#         msg = decode(raw)

#         if msg.get("type") != MsgType.LOGIN:
#             await ws.send(encode(ErrorMsg(reason="expected login")))
#             return

#         user = authenticate(msg.get("name", ""), msg.get("password", ""))
#         if user is None:
#             await ws.send(encode(ErrorMsg(reason="invalid credentials")))
#             return

#         await ws.send(encode(OkMsg(range=user.range)))
#         await ws.send(encode(LeaderboardMsg(
#             entries=[{"name": n, "range": r} for n, r in get_leaderboard(10)]
#         )))

#         # Check if this user is reconnecting to an active game
#         done_future = await handle_reconnect(user.name, ws)
#         if done_future is not None:
#             await done_future  # keep ws alive until game ends
#             return

#         # New connection — queue for matchmaking
#         await ws.send(encode(WaitingMsg()))
#         matchmaker.register(user, ws)

#         result = None
#         while result is None:
#             result = await asyncio.get_event_loop().run_in_executor(
#                 None, matchmaker.poll, ws
#             )
#             if result is None:
#                 await asyncio.sleep(0.5)

#         user_a, ws_a, user_b, ws_b = result
#         if user_a.range >= user_b.range:
#             white_user, white_ws = user_a, ws_a
#             black_user, black_ws = user_b, ws_b
#         else:
#             white_user, white_ws = user_b, ws_b
#             black_user, black_ws = user_a, ws_a

#         await run_game(white_user, white_ws, black_user, black_ws)

#     except Exception as e:
#         print(f"[server] error: {e}")


# async def main():
#     init_db()
#     print(f"[server] listening on ws://{HOST}:{PORT}")
#     async with websockets.serve(_handle_client, HOST, PORT):
#         await asyncio.Future()


# if __name__ == "__main__":
#     asyncio.run(main())

import os
import sys
import asyncio
import websockets


def build_candidate_ports(start_port=5555, max_attempts=10):
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

HOST = "0.0.0.0"
PORT = 5555

matchmaker = Matchmaker()
room_manager = RoomManager()


def translate_legacy_choice(choice):
    """ממיר בחירות מספריות של הלקוח למחרוזות הפקודה של השרת במידת הצורך"""
    if choice == 1 or choice == "1" or choice == "leaderboard":
        return "leaderboard"
    if choice == 2 or choice == "2" or choice == "match":
        return "match"
    if choice == 3 or choice == "3" or choice == "create_room":
        return "create_room"
    if choice == 4 or choice == "4" or choice == "join_room":
        return "join_room"
    if choice == "back" or choice == 0 or choice == "0":
        return "back"
    return choice


async def _handle_client(ws) -> None:
    user = None
    try:
        raw = await ws.recv()
        msg = decode(raw)

        if msg.get("type") != MsgType.LOGIN:
            await ws.send(encode(ErrorMsg(reason="expected login")))
            return

        user = authenticate(msg.get("name", ""), msg.get("password", ""))
        if user is None:
            await ws.send(encode(ErrorMsg(reason="invalid credentials")))
            return

        await ws.send(encode(OkMsg(range=user.range)))
        await ws.send(encode(LeaderboardMsg(
            entries=[{"name": n, "range": r} for n, r in get_leaderboard(10)]
        )))

        while True:
            menu_raw = await ws.recv()
            menu_msg = decode(menu_raw)
            raw_choice = menu_msg.get("choice") or menu_msg.get("selection")
            choice = translate_legacy_choice(raw_choice)

            if choice == "leaderboard":
                await ws.send(encode(LeaderboardMsg(
                    entries=[{"name": n, "range": r} for n, r in get_leaderboard(10)]
                )))
                continue

            elif choice == "match":
                done_future = await handle_reconnect(user.name, ws)
                if done_future is not None:
                    await done_future
                    continue

                await ws.send(encode(WaitingMsg()))
                matchmaker.register(user, ws)

                result = None
                while result is None:
                    try:
                        done, pending = await asyncio.wait({asyncio.ensure_future(ws.recv())}, timeout=0.1)
                        for t in pending:
                            t.cancel()
                        if done:
                            sub_msg = decode(list(done)[0].result())
                            if translate_legacy_choice(sub_msg.get("choice")) == "back":
                                matchmaker.unregister(ws)
                                result = False
                                break
                    except Exception:
                        pass

                    if result is False:
                        break

                    result = await asyncio.get_event_loop().run_in_executor(
                        None, matchmaker.poll, ws
                    )
                    if result is None:
                        await asyncio.sleep(0.5)

                if result in (False, None):
                    continue

                user_a, ws_a, user_b, ws_b = result
                if user_a.range >= user_b.range:
                    white_user, white_ws = user_a, ws_a
                    black_user, black_ws = user_b, ws_b
                else:
                    white_user, white_ws = user_b, ws_b
                    black_user, black_ws = user_a, ws_a

                await run_game(white_user, white_ws, black_user, black_ws)
                continue

            elif choice == "create_room":
                password = menu_msg.get("password", "")
                room_id = room_manager.create_room(password, ws)
                room = room_manager._rooms.get(room_id)
                room.users[ws] = user

                await ws.send(encode({"type": MsgType.OK, "room_id": room_id, "message": "Room created, waiting for player..."}))

                try:
                    await asyncio.wait_for(room.ready.wait(), timeout=300)
                except asyncio.TimeoutError:
                    room_manager.remove_player(ws)
                    continue

                room = room_manager._rooms.get(room_id)
                if room and len(room.players) == 2:
                    p1_ws, p2_ws = room.players[0], room.players[1]
                    user1, user2 = room.users.get(p1_ws), room.users.get(p2_ws)
                    if user1 and user2:
                        if user1.range >= user2.range:
                            white_user, white_ws = user1, p1_ws
                            black_user, black_ws = user2, p2_ws
                        else:
                            white_user, white_ws = user2, p2_ws
                            black_user, black_ws = user1, p1_ws
                        viewer_wss = list(room.viewers)
                        await run_game(white_user, white_ws, black_user, black_ws, viewer_wss=viewer_wss)
                continue

            elif choice == "join_room":
                room_id = menu_msg.get("room_id")
                password = menu_msg.get("password", "")

                role, message = room_manager.join_room(room_id, password, ws)
                if not role:
                    await ws.send(encode(ErrorMsg(reason=message)))
                    continue

                room = room_manager._rooms.get(room_id)
                if room is None:
                    continue
                room.users[ws] = user
                await ws.send(encode({"type": MsgType.OK, "room_id": room_id, "role": role, "message": message}))

                if len(room.players) == 2:
                    room.ready.set()

                if role == "viewer":
                    continue

            elif choice == "back":
                continue

    except Exception as e:
        print(f"[server] error: {e}")
    finally:
        try:
            matchmaker.unregister(ws)
        except Exception:
            pass

        try:
            room_manager.remove_player(ws)
        except Exception:
            pass


async def main():
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
            continue

    if last_exc is not None:
        print(f"[server] failed to start: {last_exc}")
        raise last_exc


if __name__ == "__main__":
    asyncio.run(main())