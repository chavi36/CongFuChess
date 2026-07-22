"""
server.py — WebSocket entry point.

Login flow:
  1. Client sends LoginMsg.
  2. Server authenticates and responds OkMsg.
  3. If the user has a game waiting for reconnection, they are routed back in.
  4. Otherwise they are queued in the matchmaker and sent WaitingMsg.
"""

import asyncio
import websockets

from application.server.db.db import authenticate, init_db, get_leaderboard
from application.server.matchmaker import Matchmaker
from application.server.game_server import run_game, handle_reconnect
from application.server.protocol import encode, decode, ErrorMsg, OkMsg, WaitingMsg, LeaderboardMsg
from Core.model.config import MsgType

HOST = "0.0.0.0"
PORT = 5555

matchmaker = Matchmaker()


async def _handle_client(ws) -> None:
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

        # Check if this user is reconnecting to an active game
        done_future = await handle_reconnect(user.name, ws)
        if done_future is not None:
            await done_future  # keep ws alive until game ends
            return

        # New connection — queue for matchmaking
        await ws.send(encode(WaitingMsg()))
        matchmaker.register(user, ws)

        result = None
        while result is None:
            result = await asyncio.get_event_loop().run_in_executor(
                None, matchmaker.poll, ws
            )
            if result is None:
                await asyncio.sleep(0.5)

        user_a, ws_a, user_b, ws_b = result
        if user_a.range >= user_b.range:
            white_user, white_ws = user_a, ws_a
            black_user, black_ws = user_b, ws_b
        else:
            white_user, white_ws = user_b, ws_b
            black_user, black_ws = user_a, ws_a

        await run_game(white_user, white_ws, black_user, black_ws)

    except Exception as e:
        print(f"[server] error: {e}")


async def main():
    init_db()
    print(f"[server] listening on ws://{HOST}:{PORT}")
    async with websockets.serve(_handle_client, HOST, PORT):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
