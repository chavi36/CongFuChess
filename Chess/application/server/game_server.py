# """
# game_server.py — runs one GameSession between two connected clients.

# White = the player with the higher mark (or first if equal).
# Ticks the engine at TICK_MS intervals, relays click/jump from each client,
# and pushes a snapshot to both after every tick.
# Updates ELO in the DB when the game ends.
# """

# import os
# import threading
# import time
# from dataclasses import asdict

# from application.bridge.game_session import GameSession
# from kungfu_chess.model.config import PieceColor
# from kungfu_chess.model.player import Player
# from application.server.db import update_after_game
# from application.server.protocol import encode, decode

# TICK_MS  = 30
# BOARD_CSV = os.path.join(os.path.dirname(__file__), "..", "..", "kungfu_chess",
#                          "anotations", "pieces1", "board.csv")


# def _send(conn, msg: dict) -> None:
#     try:
#         conn.sendall(encode(msg))
#     except OSError:
#         pass


# def _snapshot_dict(session: GameSession) -> dict:
#     snap = session.get_render_snapshot()
#     return {
#         "type": "snapshot",
#         "clock": snap.clock,
#         "board": snap.board,
#         "board_width": snap.board_width,
#         "board_height": snap.board_height,
#         "active_moves": [asdict(m) for m in snap.active_moves],
#         "cooldowns":    [asdict(c) for c in snap.cooldowns],
#         "game_over":    snap.game_over,
#         "winner":       snap.winner,
#     }


# def _read_loop(conn, session: GameSession, color: str, stop: threading.Event) -> None:
#     """Read commands from one client and forward them to the session."""
#     buf = b""
#     while not stop.is_set():
#         try:
#             chunk = conn.recv(1024)
#         except OSError:
#             break
#         if not chunk:
#             break
#         buf += chunk
#         while b"\n" in buf:
#             line, buf = buf.split(b"\n", 1)
#             try:
#                 msg = decode(line + b"\n")
#             except Exception:
#                 continue
#             if msg.get("type") == "click":
#                 session.click(msg["row"], msg["col"])
#             elif msg.get("type") == "jump":
#                 session.jump(msg["row"], msg["col"])
#     stop.set()


# def run_game(user_white: dict, conn_white,
#              user_black: dict, conn_black) -> None:
#     """Entry point called by the server for each matched pair."""
#     white = Player(name=user_white["name"], color=PieceColor.WHITE)
#     black = Player(name=user_black["name"], color=PieceColor.BLACK)

#     session = GameSession(BOARD_CSV, white, black)

#     # tell each client who they are and who their opponent is
#     _send(conn_white, {"type": "matched", "color": "white",
#                        "opponent": user_black["name"],
#                        "opponent_range": user_black["range"]})
#     _send(conn_black, {"type": "matched", "color": "black",
#                        "opponent": user_white["name"],
#                        "opponent_range": user_white["range"]})

#     stop = threading.Event()
#     threading.Thread(target=_read_loop,
#                      args=(conn_white, session, "w", stop), daemon=True).start()
#     threading.Thread(target=_read_loop,
#                      args=(conn_black, session, "b", stop), daemon=True).start()

#     last_tick = time.monotonic()
#     while not stop.is_set():
#         now     = time.monotonic()
#         elapsed = int((now - last_tick) * 1000)
#         if elapsed >= TICK_MS:
#             session.tick(elapsed)
#             last_tick = now
#             snap = _snapshot_dict(session)
#             _send(conn_white, snap)
#             _send(conn_black, snap)
#             if session.is_over():
#                 break
#         else:
#             time.sleep(0.001)

#     stop.set()

#     # update ELO
#     winner_name = session.winner()
#     if winner_name:
#         if winner_name == user_white["name"]:
#             update_after_game(user_white["name"], user_white["range"],
#                               user_black["name"], user_black["range"])
#         else:
#             update_after_game(user_black["name"], user_black["range"],
#                               user_white["name"], user_white["range"])



import os
import socket
import threading
import time
from dataclasses import asdict

from application.bridge.game_session import GameSession
from kungfu_chess.model.config import PieceColor
from kungfu_chess.model.player import Player
from application.server.db import update_after_game
from application.server.protocol import encode, decode

TICK_MS  = 30
BOARD_CSV = os.path.join(os.path.dirname(__file__), "..", "..", "kungfu_chess",
                         "anotations", "pieces1", "board.csv")

def _snapshot_dict(session: GameSession) -> dict:
    snap = session.get_render_snapshot()
    return {
        "type": "snapshot",
        "clock": snap.clock,
        "board": snap.board,
        "board_width": snap.board_width,
        "board_height": snap.board_height,
        "active_moves": [asdict(m) for m in snap.active_moves],
        "cooldowns":    [asdict(c) for c in snap.cooldowns],
        "game_over":    snap.game_over,
        "winner":       snap.winner,
    }


def _send(conn, msg: dict) -> None:
    try:
        conn.sendall(encode(msg))
    except OSError:
        pass

def _read_loop(conn, session: GameSession, color: str, stop: threading.Event,
               last_activity: dict, activity_lock: threading.Lock) -> None:
    """Read commands from one client and forward them to the session."""
    buf = b""
    while not stop.is_set():
        try:
            conn.settimeout(1.0)
            chunk = conn.recv(1024)
        except socket.timeout:
            continue
        except OSError:
            break

        if not chunk:
            break

        with activity_lock:
            last_activity[conn] = time.time()

        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            try:
                msg = decode(line + b"\n")
            except Exception:
                continue
            if msg.get("type") == "click":
                session.click(msg["row"], msg["col"])
            elif msg.get("type") == "jump":
                session.jump(msg["row"], msg["col"])
    stop.set()

def run_game(user_white: dict, conn_white,
             user_black: dict, conn_black) -> None:

    last_activity = {}
    activity_lock = threading.Lock()
    with activity_lock:
        last_activity[conn_white] = time.time()
        last_activity[conn_black] = time.time()

    white = Player(name=user_white["name"], color=PieceColor.WHITE)
    black = Player(name=user_black["name"], color=PieceColor.BLACK)

    session = GameSession(BOARD_CSV, white, black)

    _send(conn_white, {"type": "matched", "color": "white",
                       "opponent": user_black["name"],
                       "opponent_range": user_black["range"]})
    _send(conn_black, {"type": "matched", "color": "black",
                       "opponent": user_white["name"],
                       "opponent_range": user_white["range"]})

    stop = threading.Event()
    threading.Thread(target=_read_loop,
                     args=(conn_white, session, "w", stop, last_activity, activity_lock),
                     daemon=True).start()
    threading.Thread(target=_read_loop,
                     args=(conn_black, session, "b", stop, last_activity, activity_lock),
                     daemon=True).start()

    last_tick = time.monotonic()
    while not stop.is_set():
        now_time = time.time()
        with activity_lock:
            if (now_time - last_activity.get(conn_white, now_time) > 20) or \
               (now_time - last_activity.get(conn_black, now_time) > 20):
                print("Client disconnected via timeout.")
                break

        now = time.monotonic()
        elapsed = int((now - last_tick) * 1000)
        if elapsed >= TICK_MS:
            session.tick(elapsed)
            last_tick = now
            snap = _snapshot_dict(session)
            _send(conn_white, snap)
            _send(conn_black, snap)
            if session.is_over():
                break
        time.sleep(0.01)

    stop.set()

    winner_name = session.winner()
    if winner_name:
        if winner_name == user_white["name"]:
            update_after_game(user_white["name"], user_white["range"],
                              user_black["name"], user_black["range"])
        else:
            update_after_game(user_black["name"], user_black["range"],
                              user_white["name"], user_white["range"])