"""
game_server.py — runs one GameSession between two connected WebSocket clients.

- Each player can only move their own pieces (enforced via GameSession.click_as/jump_as).
- Viewers receive snapshots but all their actions are silently ignored.
- On disconnect, the opponent is notified and the player has RECONNECT_TIMEOUT_S to reconnect.
- On timeout, the opponent wins by forfeit and both connections are closed.
"""

import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from queue import Queue, Empty

from application.bridge.game_session import GameSession
from Core.model.config import PieceColor, RECONNECT_TIMEOUT_S
from Core.model.player import Player
from application.server.db.db import UserRecord, update_after_game, compute_elo
from application.server.protocol import (
    encode, decode_client_msg,
    MatchedMsg, SnapshotMsg, DisconnectedMsg, ReconnectedMsg, ForfeitMsg, GameOverMsg,
)
from application.path_utils import resolve_pieces_dir
from Core.model.config import CommandType, MsgType

TICK_MS   = 30
BOARD_CSV = os.path.join(resolve_pieces_dir(__file__), "pieces1", "board.csv")

_executor = ThreadPoolExecutor(max_workers=4)

# Registry: username -> (asyncio.Queue, MatchedMsg, asyncio.Future)
# Queue receives the new ws; Future is resolved when the game session ends.
_reconnect_registry: dict = {}


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
        white_score=session.white.score,
        black_score=session.black.score,
    )


def _sync_game_loop(session: GameSession, inbound: Queue, outbound: Queue) -> None:
    """
    Purely synchronous game loop — runs in a thread, never touches the event loop.
    Each action carries a 'role' ('white'|'black') so GameSession can enforce ownership.
    """
    last_tick = time.monotonic()
    while True:
        while True:
            try:
                action = inbound.get_nowait()
                if action is None:      # shutdown signal
                    return
                role = action.get("role")
                if action["type"] == CommandType.CLICK:
                    session.click_as(role, action["row"], action["col"])
                elif action["type"] == CommandType.JUMP:
                    session.jump_as(role, action["row"], action["col"])
            except Empty:
                break

        now = time.monotonic()
        elapsed = int((now - last_tick) * 1000)
        if elapsed >= TICK_MS:
            session.tick(elapsed)
            last_tick = now
            outbound.put(_snapshot_msg(session))
            if session.is_over():
                outbound.put(None)  # game-over signal
                return

        time.sleep(0.001)


async def _read_loop(ws, role: str, inbound: Queue, stop: asyncio.Event) -> None:
    """Reads from one player's WebSocket and tags every action with their role."""
    try:
        async for raw in ws:
            if stop.is_set():
                return
            try:
                msg = decode_client_msg(raw)
                inbound.put({
                    "type": msg.type,
                    "role": role,
                    "row":  getattr(msg, "row", None),
                    "col":  getattr(msg, "col", None),
                })
            except Exception:
                continue
    except Exception:
        pass
    # NOTE: do NOT set stop here — a single disconnect should not tear down the game


async def _broadcast_loop(
    ws_slots: dict,         # {"white": ws | None, "black": ws | None}
    outbound: Queue,
    stop: asyncio.Event,
) -> None:
    """Drains outbound snapshots and sends to whichever connections are currently live."""
    while not stop.is_set():
        try:
            snap = outbound.get_nowait()
            if snap is None:
                stop.set()
                return
            encoded = encode(snap)
            coros = [
                ws.send(encoded)
                for ws in ws_slots.values()
                if ws is not None
            ]
            if coros:
                await asyncio.gather(*coros, return_exceptions=True)
        except Empty:
            await asyncio.sleep(0.001)


async def _notify_both(ws_slots: dict, msg) -> None:
    encoded = encode(msg)
    coros = [ws.send(encoded) for ws in ws_slots.values() if ws is not None]
    if coros:
        await asyncio.gather(*coros, return_exceptions=True)


async def _handle_disconnect(
    disconnected_role: str,
    opponent_role: str,
    ws_slots: dict,
    inbound: Queue,
    stop: asyncio.Event,
    user_name: str,
    matched_msg: MatchedMsg,
) -> str | None:
    """
    Notifies the opponent, waits up to RECONNECT_TIMEOUT_S for the player to reconnect.
    Returns the new ws if reconnected, or None on timeout.
    Sends countdown updates every second.
    """
    reconnect_queue: asyncio.Queue = asyncio.Queue()
    done_future: asyncio.Future = asyncio.get_event_loop().create_future()
    _reconnect_registry[user_name] = (reconnect_queue, matched_msg, done_future)

    try:
        deadline = time.monotonic() + RECONNECT_TIMEOUT_S
        while True:
            remaining = int(deadline - time.monotonic())
            if remaining <= 0:
                return None

            # notify opponent of countdown
            opp_ws = ws_slots.get(opponent_role)
            if opp_ws:
                try:
                    await opp_ws.send(encode(DisconnectedMsg(
                        player=user_name,
                        seconds_remaining=remaining,
                    )))
                except Exception:
                    pass

            try:
                new_ws = await asyncio.wait_for(reconnect_queue.get(), timeout=1.0)
                return new_ws
            except asyncio.TimeoutError:
                continue
    finally:
        _reconnect_registry.pop(user_name, None)


async def run_game(
    user_white: UserRecord, ws_white,
    user_black: UserRecord, ws_black,
) -> None:
    white  = Player(name=user_white.name, color=PieceColor.WHITE)
    black  = Player(name=user_black.name, color=PieceColor.BLACK)
    session = GameSession(BOARD_CSV, white, black)

    # ws_slots is mutable so _broadcast_loop always uses the current connection
    ws_slots = {"white": ws_white, "black": ws_black}

    try:
        await ws_white.send(encode(MatchedMsg(
            color="white", opponent=user_black.name, opponent_range=user_black.range
        )))
        await ws_black.send(encode(MatchedMsg(
            color="black", opponent=user_white.name, opponent_range=user_white.range
        )))
    except Exception as e:
        print(f"[game_server] Failed to send match messages: {e}")
        return

    inbound:  Queue = Queue()
    outbound: Queue = Queue()
    stop      = asyncio.Event()
    loop      = asyncio.get_running_loop()

    game_future = loop.run_in_executor(_executor, _sync_game_loop, session, inbound, outbound)
    broadcast_task = asyncio.create_task(
        _broadcast_loop(ws_slots, outbound, stop)
    )

    forfeit_winner: str | None = None
    matched_msgs = {
        "white": MatchedMsg(color="white", opponent=user_black.name, opponent_range=user_black.range),
        "black": MatchedMsg(color="black", opponent=user_white.name, opponent_range=user_white.range),
    }

    async def player_lifecycle(role: str, user: UserRecord, initial_ws) -> None:
        nonlocal forfeit_winner
        current_ws = initial_ws
        opponent_role = "black" if role == "white" else "white"

        while not stop.is_set():
            read_task   = asyncio.ensure_future(_read_loop(current_ws, role, inbound, stop))
            stop_task   = asyncio.ensure_future(stop.wait())
            done, _     = await asyncio.wait(
                {read_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
            )
            read_task.cancel()
            stop_task.cancel()

            if stop.is_set():
                break

            # if game ended naturally, don't treat the closing ws as a disconnect
            if session.is_over():
                break

            # connection dropped — attempt reconnect
            ws_slots[role] = None
            new_ws = await _handle_disconnect(
                role, opponent_role, ws_slots, inbound, stop, user.name, matched_msgs[role]
            )

            if new_ws is None:
                # timeout — opponent wins by forfeit
                opponent_name = (user_white if role == "black" else user_black).name
                forfeit_winner = opponent_name
                await _notify_both(ws_slots, ForfeitMsg(
                    winner=opponent_name,
                    reason=f"{user.name} disconnected",
                ))
                stop.set()
                break

            # reconnected — swap in new ws and notify both players
            ws_slots[role] = new_ws
            await _notify_both(ws_slots, ReconnectedMsg(player=user.name))
            current_ws = new_ws

    await asyncio.gather(
        player_lifecycle("white", user_white, ws_white),
        player_lifecycle("black", user_black, ws_black),
    )

    inbound.put(None)   # shutdown sync thread
    await game_future
    broadcast_task.cancel()

    # resolve any pending reconnect futures so server.py can release those ws connections
    for name in (user_white.name, user_black.name):
        entry = _reconnect_registry.pop(name, None)
        if entry:
            _, _, done_future = entry
            if not done_future.done():
                done_future.set_result(None)

    winner_name = forfeit_winner or session.winner()
    if winner_name:
        winner_rec = user_white if winner_name == user_white.name else user_black
        loser_rec  = user_black if winner_name == user_white.name else user_white
        update_after_game(winner_rec.name, winner_rec.range, loser_rec.name, loser_rec.range)
        new_winner_elo, new_loser_elo = compute_elo(winner_rec.range, loser_rec.range)
        for role, user_rec in (("white", user_white), ("black", user_black)):
            ws = ws_slots.get(role)
            if ws:
                elo = new_winner_elo if user_rec.name == winner_name else new_loser_elo
                try:
                    await ws.send(encode(GameOverMsg(winner=winner_name, new_elo=elo)))
                except Exception:
                    pass


async def handle_reconnect(user_name: str, new_ws) -> asyncio.Future | None:
    """
    Called by server.py when a logged-in user reconnects.
    Sends MatchedMsg so the client can rebuild its GUI, then hands ws to the game.
    Returns a Future to await (keeps ws alive) or None if not reconnecting.
    """
    entry = _reconnect_registry.get(user_name)
    if entry is None:
        return None
    queue, matched_msg, done_future = entry
    await new_ws.send(encode(matched_msg))
    await queue.put(new_ws)
    return done_future
