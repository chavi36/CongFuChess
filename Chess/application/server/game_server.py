# """
# game_server.py — runs one GameSession between two connected WebSocket clients.
# """

# import asyncio
# import os
# import time
# from dataclasses import asdict

# from application.bridge.game_session import GameSession
# from kungfu_chess.model.config import PieceColor
# from kungfu_chess.model.player import Player
# from kungfu_chess.db.db import UserRecord
# from application.server.db import update_after_game
# from application.server.protocol import encode, decode_client_msg, MatchedMsg, SnapshotMsg
# from application.path_utils import resolve_project_path, resolve_pieces_dir

# TICK_MS   = 30
# BOARD_CSV = os.path.join(resolve_pieces_dir(__file__), "pieces1", "board.csv")


# def _snapshot_msg(session: GameSession) -> SnapshotMsg:
#     snap = session.get_render_snapshot()
#     return SnapshotMsg(
#         clock=snap.clock,
#         board=snap.board,
#         board_width=snap.board_width,
#         board_height=snap.board_height,
#         active_moves=[asdict(m) for m in snap.active_moves],
#         cooldowns=[asdict(c) for c in snap.cooldowns],
#         game_over=snap.game_over,
#         winner=snap.winner,
#     )


# async def _read_loop(ws, session: GameSession, stop: asyncio.Event) -> None:
#     try:
#         async for raw in ws:
#             if stop.is_set():
#                 break
#             try:
#                 msg = decode_client_msg(raw)
#             except Exception:
#                 continue
#             if msg.type == "click":
#                 session.click(msg.row, msg.col)
#             elif msg.type == "jump":
#                 session.jump(msg.row, msg.col)
#     except Exception:
#         pass
#     finally:
#         stop.set()


# async def run_game(user_white: UserRecord, ws_white,
#                    user_black: UserRecord, ws_black) -> None:
#     white = Player(name=user_white.name, color=PieceColor.WHITE)
#     black = Player(name=user_black.name, color=PieceColor.BLACK)

#     session = GameSession(BOARD_CSV, white, black)

#     await ws_white.send(encode(MatchedMsg(
#         color="white", opponent=user_black.name, opponent_range=user_black.range
#     )))
#     await ws_black.send(encode(MatchedMsg(
#         color="black", opponent=user_white.name, opponent_range=user_white.range
#     )))

#     stop = asyncio.Event()
#     asyncio.ensure_future(_read_loop(ws_white, session, stop))
#     asyncio.ensure_future(_read_loop(ws_black, session, stop))

#     last_tick = time.monotonic()
#     while not stop.is_set():
#         now     = time.monotonic()
#         elapsed = int((now - last_tick) * 1000)
#         if elapsed >= TICK_MS:
#             session.tick(elapsed)
#             last_tick = now
#             snap = _snapshot_msg(session)
#             await asyncio.gather(
#                 ws_white.send(encode(snap)),
#                 ws_black.send(encode(snap)),
#                 return_exceptions=True,
#             )
#             if session.is_over():
#                 break
#         await asyncio.sleep(0.001)

#     stop.set()

#     winner_name = session.winner()
#     if winner_name:
#         if winner_name == user_white.name:
#             update_after_game(user_white.name, user_white.range,
#                               user_black.name, user_black.range)
#         else:
#             update_after_game(user_black.name, user_black.range,
#                               user_white.name, user_white.range)


"""
game_server.py — runs one GameSession between two connected WebSocket clients.
"""

import asyncio
import os
import time
from dataclasses import asdict

from application.bridge.game_session import GameSession
from kungfu_chess.model.config import PieceColor
from kungfu_chess.model.player import Player
from kungfu_chess.db.db import UserRecord
from application.server.db import update_after_game
from application.server.protocol import encode, decode_client_msg, MatchedMsg, SnapshotMsg
from application.path_utils import resolve_project_path, resolve_pieces_dir

TICK_MS   = 30
BOARD_CSV = os.path.join(resolve_pieces_dir(__file__), "pieces1", "board.csv")


def _snapshot_msg(session: GameSession) -> SnapshotMsg:
    snap = session.get_render_snapshot()
    return SnapshotMsg(
        clock=snap.clock,
        board=snap.board,
        board_width=snap.board_width,
        board_height=snap.board_height,
        active_moves=[asdict(m) for m in snap.active_moves],
        cooldowns=[asdict(c) for c in snap.cooldowns],
        game_over=snap.game_over,
        winner=snap.winner,
    )


async def _read_loop(ws, session: GameSession, stop: asyncio.Event) -> None:
    try:
        async for raw in ws:
            if stop.is_set():
                break
            try:
                msg = decode_client_msg(raw)
            except Exception:
                continue
            if msg.type == "click":
                session.click(msg.row, msg.col)
            elif msg.type == "jump":
                session.jump(msg.row, msg.col)
    except Exception:
        pass
    finally:
        stop.set()


async def run_game(user_white: UserRecord, ws_white,
                   user_black: UserRecord, ws_black) -> None:
    white = Player(name=user_white.name, color=PieceColor.WHITE)
    black = Player(name=user_black.name, color=PieceColor.BLACK)

    session = GameSession(BOARD_CSV, white, black)

    # שליחת הודעת התאמה לבן, תוך בדיקה שהחיבור פתוח
    try:
        await ws_white.send(encode(MatchedMsg(
            color="white", opponent=user_black.name, opponent_range=user_black.range
        )))
    except Exception as e:
        print(f"[game_server] Failed to send match message to white: {e}")
        return

    # שליחת הודעת התאמה לשחור, תוך בדיקה שהחיבור פתוח
    try:
        await ws_black.send(encode(MatchedMsg(
            color="black", opponent=user_white.name, opponent_range=user_white.range
        )))
    except Exception as e:
        print(f"[game_server] Failed to send match message to black: {e}")
        return

    stop = asyncio.Event()
    asyncio.ensure_future(_read_loop(ws_white, session, stop))
    asyncio.ensure_future(_read_loop(ws_black, session, stop))

    last_tick = time.monotonic()
    while not stop.is_set():
        now     = time.monotonic()
        elapsed = int((now - last_tick) * 1000)
        if elapsed >= TICK_MS:
            session.tick(elapsed)
            last_tick = now
            snap = _snapshot_msg(session)
            await asyncio.gather(
                ws_white.send(encode(snap)),
                ws_black.send(encode(snap)),
                return_exceptions=True,
            )
            if session.is_over():
                break
        await asyncio.sleep(0.001)

    stop.set()

    winner_name = session.winner()
    if winner_name:
        if winner_name == user_white.name:
            update_after_game(user_white.name, user_white.range,
                              user_black.name, user_black.range)
        else:
            update_after_game(user_black.name, user_black.range,
                              user_white.name, user_white.range)