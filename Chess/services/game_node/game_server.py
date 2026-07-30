"""
game_server.py — runs one GameSession between two connected WebSocket clients.

- Each player can only move their own pieces (enforced via GameSession.click_as/jump_as).
- Viewers receive snapshots but all their actions are silently ignored.
- On disconnect the game PAUSES (sync loop stops ticking) and the opponent sees a countdown.
- The disconnected player has RECONNECT_TIMEOUT_S (10 s) to reconnect.
- On reconnect: MatchedMsg is resent so the client rebuilds its GUI, game resumes.
- On timeout: opponent wins by forfeit, GameOverMsg sent to all.
"""

import asyncio
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from queue import Queue, Empty

from application.bridge.game_session import GameSession
from Core.model.config import PieceColor, RECONNECT_TIMEOUT_S
from Core.model.player import Player
from services.auth import UserRecord, update_after_game, compute_elo
from services.spectator_relay import relay_frame
from services.result_writer import write_result
from shared.protocol import (
    encode, decode_client_msg,
    MatchedMsg, SnapshotMsg, DisconnectedMsg, ReconnectedMsg, ForfeitMsg, GameOverMsg,
)
from application.path_utils import resolve_pieces_dir
from Core.model.config import CommandType, MsgType

TICK_MS   = 30
BOARD_CSV = os.path.join(resolve_pieces_dir(__file__), "pieces1", "board.csv")

_executor = ThreadPoolExecutor(max_workers=4)

# Registry: username -> (asyncio.Queue, MatchedMsg, asyncio.Future)
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


def _collect_ws_targets(ws_slots: dict, viewer_wss: list) -> list:
    targets = [ws_slots.get("white"), ws_slots.get("black")] + list(viewer_wss)
    return [ws for ws in targets if ws is not None]


def _sync_game_loop(session: GameSession, inbound: Queue, outbound: Queue,
                    paused: list) -> None:
    """
    Synchronous game loop in a thread.
    paused is a one-element list used as a mutable flag: paused[0] = True freezes ticking.
    """
    last_tick = time.monotonic()
    while True:
        # drain inbound actions
        while True:
            try:
                action = inbound.get_nowait()
                if action is None:      # shutdown signal
                    return
                role = action.get("role")
                action_type = action.get("type")
                try:
                    if action_type == CommandType.CLICK:
                        session.click_as(role, action.get("row"), action.get("col"))
                    elif action_type == CommandType.JUMP:
                        session.jump_as(role, action.get("row"), action.get("col"))
                except PermissionError:
                    pass
            except Empty:
                break

        if paused[0]:
            # game is frozen — don't tick, but keep the thread alive
            time.sleep(0.01)
            last_tick = time.monotonic()  # reset so we don't burst on resume
            continue

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
    """Reads from one WebSocket and pushes actions into inbound queue."""
    try:
        async for raw in ws:
            if stop.is_set():
                return
            try:
                msg = decode_client_msg(raw)   # returns a dict
                action_type = msg.get("type")
                if action_type in (CommandType.CLICK, CommandType.JUMP):
                    inbound.put({
                        "type": action_type,
                        "role": role,
                        "row":  msg.get("row"),
                        "col":  msg.get("col"),
                    })
            except Exception:
                continue
    except Exception:
        pass


async def _broadcast_loop(ws_slots: dict, viewer_wss: list,
                          outbound: Queue, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            snap = outbound.get_nowait()
            if snap is None:
                stop.set()
                return
            encoded = encode(snap)
            relay_frame(asdict(snap))
            targets = _collect_ws_targets(ws_slots, viewer_wss)
            if targets:
                await asyncio.gather(*[ws.send(encoded) for ws in targets],
                                     return_exceptions=True)
        except Empty:
            await asyncio.sleep(0.001)


async def _notify_targets(ws_slots: dict, viewer_wss: list, msg) -> None:
    encoded = encode(msg)
    targets = _collect_ws_targets(ws_slots, viewer_wss)
    if targets:
        await asyncio.gather(*[ws.send(encoded) for ws in targets],
                             return_exceptions=True)


async def _handle_disconnect(
    role: str,
    opponent_role: str,
    ws_slots: dict,
    viewer_wss: list,
    paused: list,
    stop: asyncio.Event,
    user_name: str,
    matched_msg: MatchedMsg,
) -> object:
    """
    Freeze the game, notify opponent with countdown every second.
    Returns new_ws if player reconnects within RECONNECT_TIMEOUT_S, else None.
    """
    paused[0] = True
    reconnect_queue: asyncio.Queue = asyncio.Queue()
    done_future = asyncio.get_running_loop().create_future()
    _reconnect_registry[user_name] = (reconnect_queue, matched_msg, done_future)

    try:
        deadline = time.monotonic() + RECONNECT_TIMEOUT_S
        while True:
            remaining = int(deadline - time.monotonic())
            if remaining <= 0:
                return None

            opp_ws = ws_slots.get(opponent_role)
            if opp_ws:
                try:
                    await opp_ws.send(encode(DisconnectedMsg(
                        player=user_name,
                        seconds_remaining=remaining,
                    )))
                except Exception:
                    pass

            # also notify viewers
            for vws in list(viewer_wss):
                try:
                    await vws.send(encode(DisconnectedMsg(
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
        paused[0] = False   # resume whether reconnected or forfeited


async def run_game(
    user_white: UserRecord, ws_white,
    user_black: UserRecord, ws_black,
    viewer_wss: list | None = None,
) -> None:
    game_id = str(uuid.uuid4())
    white   = Player(name=user_white.name, color=PieceColor.WHITE)
    black   = Player(name=user_black.name, color=PieceColor.BLACK)
    session = GameSession(BOARD_CSV, white, black)

    ws_slots   = {"white": ws_white, "black": ws_black}
    viewer_wss = list(viewer_wss or [])
    paused     = [False]   # mutable flag shared with sync thread

    # Send MatchedMsg to both players and all viewers
    try:
        await ws_white.send(encode(MatchedMsg(
            color="white", opponent=user_black.name, opponent_range=user_black.range
        )))
        await ws_black.send(encode(MatchedMsg(
            color="black", opponent=user_white.name, opponent_range=user_white.range
        )))
        for vws in viewer_wss:
            try:
                await vws.send(encode(MatchedMsg(
                    color="white", opponent=user_black.name, opponent_range=user_black.range
                )))
            except Exception:
                pass
    except Exception as e:
        print(f"[game_server] Failed to send match messages: {e}")
        return

    inbound:  Queue = Queue()
    outbound: Queue = Queue()
    stop      = asyncio.Event()
    loop      = asyncio.get_running_loop()

    game_future    = loop.run_in_executor(_executor, _sync_game_loop, session, inbound, outbound, paused)
    broadcast_task = asyncio.create_task(
        _broadcast_loop(ws_slots, viewer_wss, outbound, stop)
    )

    forfeit_winner: str | None = None
    matched_msgs = {
        "white": MatchedMsg(color="white", opponent=user_black.name, opponent_range=user_black.range),
        "black": MatchedMsg(color="black", opponent=user_white.name, opponent_range=user_white.range),
    }

    async def player_lifecycle(role: str, user: UserRecord, initial_ws) -> None:
        nonlocal forfeit_winner
        current_ws    = initial_ws
        opponent_role = "black" if role == "white" else "white"

        while not stop.is_set():
            read_task = asyncio.ensure_future(_read_loop(current_ws, role, inbound, stop))
            stop_task = asyncio.ensure_future(stop.wait())
            await asyncio.wait({read_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
            read_task.cancel()
            stop_task.cancel()

            if stop.is_set() or session.is_over():
                break

            # connection dropped — freeze game and wait for reconnect
            ws_slots[role] = None
            new_ws = await _handle_disconnect(
                role, opponent_role, ws_slots, viewer_wss,
                paused, stop, user.name, matched_msgs[role],
            )

            if new_ws is None:
                # timeout — forfeit
                opponent_name = (user_white if role == "black" else user_black).name
                forfeit_winner = opponent_name
                await _notify_targets(ws_slots, viewer_wss, ForfeitMsg(
                    winner=opponent_name,
                    reason=f"{user.name} disconnected",
                ))
                stop.set()
                break

            # reconnected — resend MatchedMsg so client rebuilds GUI, then resume
            ws_slots[role] = new_ws
            try:
                await new_ws.send(encode(matched_msgs[role]))
            except Exception:
                pass
            await _notify_targets(ws_slots, viewer_wss, ReconnectedMsg(player=user.name))
            current_ws = new_ws

    await asyncio.gather(
        player_lifecycle("white", user_white, ws_white),
        player_lifecycle("black", user_black, ws_black),
    )

    inbound.put(None)   # shutdown sync thread
    await game_future
    broadcast_task.cancel()

    # resolve pending reconnect futures
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
        write_result(game_id, {
            "winner": winner_name,
            "white":  {"name": user_white.name, "range": user_white.range},
            "black":  {"name": user_black.name, "range": user_black.range},
        })
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
    Called by server.py when a logged-in user sends 'match' and is in the reconnect registry.
    Sends MatchedMsg so the client rebuilds its GUI, hands ws to the game.
    Returns a Future to await (keeps the ws alive) or None if not reconnecting.
    """
    entry = _reconnect_registry.get(user_name)
    if entry is None:
        return None
    queue, matched_msg, done_future = entry
    await new_ws.send(encode(matched_msg))
    await queue.put(new_ws)
    return done_future
