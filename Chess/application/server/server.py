"""
server.py — WebSocket entry point.

Each client connects and sends:
    {"type": "login", "name": "...", "password": "..."}

The server responds with "ok" or "error", then "waiting" until a match is found,
then hands the pair off to game_server.run_game().
"""

import asyncio
import websockets

from application.server.db import authenticate
from kungfu_chess.db.db import init_db
from application.server.matchmaker import Matchmaker
from application.server.game_server import run_game
from application.server.protocol import encode, decode, ErrorMsg, OkMsg, WaitingMsg

HOST = "0.0.0.0"
PORT = 5555

matchmaker = Matchmaker()


async def _handle_client(ws) -> None:
    try:
        # ── authentication ────────────────────────────────────────────
        raw = await ws.recv()
        msg = decode(raw)

        if msg.get("type") != "login":
            await ws.send(encode(ErrorMsg(reason="expected login")))
            return

        user = authenticate(msg.get("name", ""), msg.get("password", ""))
        if user is None:
            await ws.send(encode(ErrorMsg(reason="invalid credentials")))
            return

        await ws.send(encode(OkMsg(range=user.range)))
        await ws.send(encode(WaitingMsg()))

        # ── matchmaking — register once, then poll ─────────────────
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
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
