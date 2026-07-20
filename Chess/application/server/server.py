"""
server.py — TCP entry point.

Each client connects and sends:
    {"type": "login", "name": "...", "password": "..."}

The server responds with "ok" or "error", then "waiting" until a match is found,
then hands the pair off to game_server.run_game().
"""

import socket
import threading

from application.server.db import authenticate
from kungfu_chess.db.db import init_db
from application.server.matchmaker import Matchmaker
from application.server.game_server import run_game
from application.server.protocol import encode, decode

HOST = "0.0.0.0"
PORT = 5555


def _handle_client(conn, addr, matchmaker: Matchmaker) -> None:
    try:
        # ── authentication ────────────────────────────────────────────
        buf = b""
        while b"\n" not in buf:
            chunk = conn.recv(1024)
            if not chunk:
                return
            buf += chunk
        line, _ = buf.split(b"\n", 1)
        msg = decode(line + b"\n")

        if msg.get("type") != "login":
            conn.sendall(encode({"type": "error", "reason": "expected login"}))
            return

        user = authenticate(msg.get("name", ""), msg.get("password", ""))
        if user is None:
            conn.sendall(encode({"type": "error", "reason": "invalid credentials"}))
            return

        conn.sendall(encode({"type": "ok", "range": user["range"]}))
        conn.sendall(encode({"type": "waiting"}))

        # ── matchmaking ───────────────────────────────────────────────
        result = matchmaker.add(user, conn, addr)
        if result is None:
            return   # waiting — will be woken up when opponent arrives

        user_a, conn_a, user_b, conn_b = result
        # higher mark plays white
        if user_a["range"] >= user_b["range"]:
            white_user, white_conn = user_a, conn_a
            black_user, black_conn = user_b, conn_b
        else:
            white_user, white_conn = user_b, conn_b
            black_user, black_conn = user_a, conn_a

        threading.Thread(
            target=run_game,
            args=(white_user, white_conn, black_user, black_conn),
            daemon=True,
        ).start()

    except Exception as e:
        print(f"[server] error with {addr}: {e}")
    finally:
        pass   # conn closed by game_server when the game ends


def main():
    init_db()
    matchmaker = Matchmaker()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, PORT))
        srv.listen()
        print(f"[server] listening on {HOST}:{PORT}")
        while True:
            conn, addr = srv.accept()
            print(f"[server] connection from {addr}")
            threading.Thread(
                target=_handle_client,
                args=(conn, addr, matchmaker),
                daemon=True,
            ).start()


if __name__ == "__main__":
    main()
