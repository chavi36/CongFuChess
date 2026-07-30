# import os
# import asyncio
# import threading
# import numpy as np
# from datetime import datetime
# from queue import Queue, Empty
# from concurrent.futures import Future
# import cv2
# import websockets
# from application.server.protocol import encode, decode
# from application.gui.gui_controller import GUIController
# from application.gui.animated_renderer import AnimatedRenderer
# from application.gui.move_log_panel import (
#     draw_move_log, draw_board_labels, draw_leaderboard, PANEL_W,
# )
# from application.path_utils import resolve_pieces_dir, resolve_board_image
# from Core.model.config import (
#     MsgType, GUI_WINDOW_W, GUI_WINDOW_H, GUI_BOARD_SIZE,
#     BOARD_ROWS, BOARD_COLS,
# )

# HOST           = "127.0.0.1"
# PORT           = 5555
# PIECES_SET     = "pieces4"
# ESC_KEY        = 27
# RENDER_WAIT_MS = 30

# # ── text colours (BGR) ────────────────────────────────────────────────────────
# COLOR_WHITE_TEXT  = (255, 255, 255)
# COLOR_BLACK_TEXT  = (160, 160, 160)
# COLOR_SCORE_SELF  = (80, 220, 80)
# COLOR_SCORE_OPP   = (80, 80, 220)
# COLOR_COLOR_LABEL = (200, 180, 60)


# def _cell_to_notation(row: int, col: int) -> str:
#     return chr(ord('a') + col) + str(BOARD_ROWS - row)


# class GameClient:
#     """
#     Async network layer in a background thread.
#     Sync GUI reads snapshots and accumulated move-log entries via thread-safe state.
#     """

#     def __init__(self, host=HOST, port=PORT):
#         self.uri = f"ws://{host}:{port}"
#         self._loop = asyncio.new_event_loop()
#         self._lock = threading.Lock()

#         self._snapshot      = None
#         self._matched_info  = None
#         self._leaderboard   = []          # list of {name, range}
#         self._my_elo        = None        # set from OkMsg.range

#         # move-log entries accumulated from snapshots: {color: [(time, piece, from, to)]}
#         self._move_entries  = {"white": [], "black": []}
#         self._seen_moves    = set()       # (from_row, from_col, to_row, to_col, start_time)

#         self._outbound: Queue  = Queue()
#         self._login_result: Future = Future()

#         # disconnect / reconnect / forfeit state
#         self._disconnected_player: str | None = None
#         self._disconnected_seconds: int = 0
#         self._forfeit_info: dict | None = None
#         self._server_gone: bool = False
#         self._game_over_info: dict | None = None  # {winner, new_elo}

#     # ── async network loop ────────────────────────────────────────────

#     async def _connect_and_run(self, username: str, password: str) -> None:
#         try:
#             async with websockets.connect(self.uri) as ws:
#                 await ws.send(encode({"type": MsgType.LOGIN, "name": username, "password": password}))
#                 async for raw in ws:
#                     msg      = decode(raw)
#                     msg_type = msg.get("type")

#                     if msg_type == MsgType.OK and not self._login_result.done():
#                         with self._lock:
#                             self._my_elo = msg.get("range")
#                         self._login_result.set_result(msg)

#                     elif msg_type == MsgType.ERROR and not self._login_result.done():
#                         self._login_result.set_result(msg)

#                     elif msg_type == MsgType.LEADERBOARD:
#                         with self._lock:
#                             self._leaderboard = msg.get("entries", [])

#                     elif msg_type == MsgType.MATCHED:
#                         if not self._login_result.done():
#                             self._login_result.set_result({"type": MsgType.OK})
#                         with self._lock:
#                             self._matched_info = msg

#                     elif msg_type == MsgType.SNAPSHOT:
#                         self._ingest_snapshot(msg)

#                     elif msg_type == MsgType.DISCONNECTED:
#                         with self._lock:
#                             self._disconnected_player  = msg.get("player")
#                             self._disconnected_seconds = msg.get("seconds_remaining", 0)

#                     elif msg_type == MsgType.RECONNECTED:
#                         with self._lock:
#                             self._disconnected_player  = None
#                             self._disconnected_seconds = 0

#                     elif msg_type == MsgType.FORFEIT:
#                         with self._lock:
#                             self._forfeit_info = {
#                                 "winner": msg.get("winner"),
#                                 "reason": msg.get("reason", ""),
#                             }

#                     elif msg_type == MsgType.GAME_OVER:
#                         with self._lock:
#                             self._game_over_info = {
#                                 "winner": msg.get("winner"),
#                                 "new_elo": msg.get("new_elo"),
#                             }

#                     # drain outbound queue
#                     while True:
#                         try:
#                             await ws.send(encode(self._outbound.get_nowait()))
#                         except Empty:
#                             break
#         except Exception:
#             pass
#         finally:
#             with self._lock:
#                 self._server_gone = True
#             if not self._login_result.done():
#                 self._login_result.set_exception(ConnectionError("server disconnected"))

#     def _ingest_snapshot(self, snap: dict) -> None:
#         """Thread-safe: store snapshot and extract new move-log entries."""
#         now_str = datetime.now().strftime("%H:%M:%S")
#         with self._lock:
#             self._snapshot = snap
#             # active_moves that have already started tell us pieces in flight;
#             # we log them once when we first see them.
#             for m in snap.get("active_moves", []):
#                 key = (m["from_row"], m["from_col"], m["to_row"], m["to_col"], m["start_time"])
#                 if key in self._seen_moves:
#                     continue
#                 self._seen_moves.add(key)
#                 piece_code = m.get("piece_code", "")
#                 color      = "white" if piece_code.startswith("w") else "black"
#                 piece_type = piece_code[1] if len(piece_code) > 1 else "?"
#                 frm = _cell_to_notation(m["from_row"], m["from_col"])
#                 to  = _cell_to_notation(m["to_row"],   m["to_col"])
#                 self._move_entries[color].append((now_str, piece_type, frm, to))

#     # ── public sync API ───────────────────────────────────────────────

#     def connect_and_login(self, username: str, password: str) -> dict:
#         threading.Thread(
#             target=self._loop.run_until_complete,
#             args=(self._connect_and_run(username, password),),
#             daemon=True,
#         ).start()
#         return self._login_result.result(timeout=10)

#     def send_action(self, action_type: str, row=None, col=None) -> None:
#         msg = {"type": action_type}
#         if row is not None: msg["row"] = row
#         if col is not None: msg["col"] = col
#         self._outbound.put(msg)

#     def get_snapshot(self):
#         with self._lock:
#             return self._snapshot

#     def get_matched_info(self):
#         with self._lock:
#             return self._matched_info

#     def get_leaderboard(self):
#         with self._lock:
#             return list(self._leaderboard)

#     def get_move_entries(self, color: str):
#         with self._lock:
#             return list(self._move_entries[color])

#     def get_my_elo(self):
#         with self._lock:
#             return self._my_elo

#     def get_disconnect_state(self):
#         """Returns (player_name, seconds_remaining) or (None, 0) if no disconnect."""
#         with self._lock:
#             return self._disconnected_player, self._disconnected_seconds

#     def get_forfeit_info(self):
#         with self._lock:
#             return self._forfeit_info

#     def get_game_over_info(self):
#         with self._lock:
#             return self._game_over_info

#     def is_server_gone(self):
#         with self._lock:
#             return self._server_gone


# # ── HUD drawing helpers ───────────────────────────────────────────────────────

# def _draw_hud(canvas, snap: dict, my_name: str, opp_name: str,
#               my_color: str, my_elo, offset_y: int, board_bottom: int) -> None:
#     """Draw name / ELO / score / color label above and below the board."""
#     font = cv2.FONT_HERSHEY_SIMPLEX
#     cx   = GUI_WINDOW_W // 2

#     # my info — above board (I sit at the bottom of the screen)
#     my_score  = snap.get("white_score", 0) if my_color == "white" else snap.get("black_score", 0)
#     opp_score = snap.get("black_score", 0) if my_color == "white" else snap.get("white_score", 0)

#     elo_str  = f"  ELO {my_elo}" if my_elo is not None else ""
#     my_text  = f"{my_name} ({my_color}){elo_str}   score: {my_score}"
#     opp_text = f"{opp_name}   score: {opp_score}"

#     (tw, _), _ = cv2.getTextSize(my_text, font, 0.65, 1)
#     cv2.putText(canvas, my_text,  (cx - tw // 2, offset_y - 12), font, 0.65, COLOR_SCORE_SELF, 2)

#     (tw, _), _ = cv2.getTextSize(opp_text, font, 0.65, 1)
#     cv2.putText(canvas, opp_text, (cx - tw // 2, board_bottom + 22), font, 0.65, COLOR_SCORE_OPP, 1)


# def main():
#     name = input("Username: ")
#     pwd  = input("Password: ")

#     while True:
#         client = GameClient()

#         try:
#             resp = client.connect_and_login(name, pwd)
#         except Exception as e:
#             print(f"Could not connect or login: {e}")
#             return

#         if resp.get("type") != MsgType.OK:
#             print(f"Login failed: {resp.get('reason')}")
#             return

#         print("Waiting for opponent...")

#         pieces_dir = os.path.abspath(os.path.join(resolve_pieces_dir(__file__), PIECES_SET))
#         renderer   = AnimatedRenderer(
#             resolve_board_image(__file__), pieces_dir,
#             GUI_WINDOW_W, GUI_WINDOW_H, GUI_BOARD_SIZE,
#         )

#         matched = None
#         while matched is None:
#             matched = client.get_matched_info()

#         my_color   = matched.get("color", "white")
#         opp_name   = matched.get("opponent", "?")
#         flipped    = (my_color == "black")

#         controller = GUIController(renderer, client, flipped=flipped)

#         cv2.namedWindow("Kungfu Chess")
#         cv2.setMouseCallback("Kungfu Chess", controller.get_mouse_callback())

#         offset_y     = (GUI_WINDOW_H - GUI_BOARD_SIZE) // 2
#         board_bottom = offset_y + GUI_BOARD_SIZE
#         board_x      = (GUI_WINDOW_W - GUI_BOARD_SIZE) // 2

#         my_log_color  = (220, 220, 220) if my_color == "white" else (120, 120, 120)
#         opp_log_color = (120, 120, 120) if my_color == "white" else (220, 220, 220)
#         opp_color     = "black" if my_color == "white" else "white"

#         def _draw_overlay(canvas, lines: list[str], bg=(30, 30, 30), text_color=(220, 220, 220)) -> None:
#             h, w = canvas.shape[:2]
#             overlay = canvas.copy()
#             cv2.rectangle(overlay, (w // 4, h // 3), (3 * w // 4, 2 * h // 3), bg, -1)
#             canvas[:] = cv2.addWeighted(overlay, 0.75, canvas, 0.25, 0)
#             font = cv2.FONT_HERSHEY_SIMPLEX
#             for i, line in enumerate(lines):
#                 (tw, th), _ = cv2.getTextSize(line, font, 0.7, 2)
#                 y = h // 3 + 50 + i * (th + 18)
#                 cv2.putText(canvas, line, (w // 2 - tw // 2, y), font, 0.7, text_color, 2)

#         last_canvas = None
#         play_again  = False

#         try:
#             while True:
#                 if client.is_server_gone():
#                     break

#                 forfeit = client.get_forfeit_info()
#                 game_over = client.get_game_over_info()
#                 result = forfeit or game_over

#                 if result:
#                     snap = client.get_snapshot()
#                     canvas = renderer.render(snap, selected=None, flipped=flipped) if snap else \
#                              np.zeros((GUI_WINDOW_H, GUI_WINDOW_W, 3), dtype=np.uint8)
#                     winner = result["winner"]
#                     outcome = "You win!" if winner == name else f"{winner} wins!"
#                     lines = [outcome]
#                     if game_over and game_over.get("new_elo") is not None:
#                         lines.append(f"Your new ELO: {game_over['new_elo']}")
#                     if forfeit:
#                         lines.append(result.get("reason", ""))
#                     lines.append("ESC = quit   any key = new game")
#                     _draw_overlay(canvas, lines, bg=(20, 20, 60))
#                     cv2.imshow("Kungfu Chess", canvas)
#                     key = cv2.waitKey(0) & 0xFF
#                     if key != ESC_KEY:
#                         play_again = True
#                     break

#                 disc_player, disc_secs = client.get_disconnect_state()
#                 if disc_player:
#                     canvas = last_canvas if last_canvas is not None else \
#                              np.zeros((GUI_WINDOW_H, GUI_WINDOW_W, 3), dtype=np.uint8)
#                     canvas = canvas.copy()
#                     _draw_overlay(canvas, [
#                         f"{disc_player} disconnected",
#                         f"Waiting for reconnect... {disc_secs}s",
#                     ])
#                     cv2.imshow("Kungfu Chess", canvas)
#                     cv2.waitKey(RENDER_WAIT_MS)
#                     continue

#                 snap = client.get_snapshot()
#                 if snap:
#                     try:
#                         canvas = renderer.render(snap, selected=controller.selected, flipped=flipped)
#                     except Exception as exc:
#                         print(f"[client] render error: {exc}")
#                         canvas = None

#                     if canvas is not None:
#                         last_canvas = canvas.copy()
#                         draw_board_labels(canvas, board_x, offset_y, GUI_BOARD_SIZE, flipped=flipped)
#                         _draw_hud(canvas, snap, name, opp_name, my_color,
#                                   client.get_my_elo(), offset_y, board_bottom)
#                         draw_move_log(canvas, client.get_move_entries(my_color),
#                                       10, offset_y,
#                                       f"{name} ({my_color}) moves", my_log_color)
#                         draw_move_log(canvas, client.get_move_entries(opp_color),
#                                       GUI_WINDOW_W - PANEL_W - 10, offset_y,
#                                       f"{opp_name} ({opp_color}) moves", opp_log_color)
#                         lb = client.get_leaderboard()
#                         if lb:
#                             draw_leaderboard(canvas, lb, 10, board_bottom + 40)
#                         cv2.imshow("Kungfu Chess", canvas)
#                 else:
#                     canvas = np.zeros((GUI_WINDOW_H, GUI_WINDOW_W, 3), dtype=np.uint8)
#                     lb = client.get_leaderboard()
#                     if lb:
#                         draw_leaderboard(canvas, lb, GUI_WINDOW_W // 2 - 110, GUI_WINDOW_H // 2 - 60)
#                     cv2.putText(canvas, "Waiting for opponent...",
#                                 (GUI_WINDOW_W // 2 - 140, GUI_WINDOW_H // 2 - 80),
#                                 cv2.FONT_HERSHEY_SIMPLEX, 0.7, (180, 180, 180), 1)
#                     cv2.imshow("Kungfu Chess", canvas)

#                 if cv2.waitKey(RENDER_WAIT_MS) & 0xFF == ESC_KEY:
#                     break
#         finally:
#             cv2.destroyAllWindows()

#         if not play_again:
#             break


# if __name__ == "__main__":
#     main()



import os
import asyncio
import threading
import numpy as np
from datetime import datetime
from queue import Queue, Empty
from concurrent.futures import Future
import cv2
import websockets

from shared.protocol import encode, decode, MenuChoiceMsg
from application.gui.gui_controller import GUIController
from application.gui.animated_renderer import AnimatedRenderer
from application.gui.move_log_panel import (
    draw_move_log, draw_board_labels, draw_leaderboard, PANEL_W,
)
from application.path_utils import resolve_pieces_dir, resolve_board_image
from client.menu_state import MenuState
from Core.model.config import (
    MsgType, GUI_WINDOW_W, GUI_WINDOW_H, GUI_BOARD_SIZE,
    BOARD_ROWS, BOARD_COLS,
)

HOST           = "127.0.0.1"
PORT           = 5555
PORT_FALLBACKS = tuple(range(PORT + 1, PORT + 6))
PIECES_SET     = "pieces4"
ESC_KEY        = 27
RENDER_WAIT_MS = 30

COLOR_WHITE_TEXT  = (255, 255, 255)
COLOR_BLACK_TEXT  = (160, 160, 160)
COLOR_SCORE_SELF  = (80, 220, 80)
COLOR_SCORE_OPP   = (80, 80, 220)


def _cell_to_notation(row: int, col: int) -> str:
    return chr(ord('a') + col) + str(BOARD_ROWS - row)


class GameClient:
    def __init__(self, host=HOST, port=PORT):
        self.host = host
        self.port = port
        self.ports = [port] + [candidate for candidate in PORT_FALLBACKS if candidate != port]
        self.uri = f"ws://{host}:{self.ports[0]}"
        self._lock = threading.Lock()

        self._snapshot      = None
        self._matched_info  = None
        self._leaderboard   = []
        self._my_elo        = None
        self._created_room_id = None  # שמירת ה-ID של החדר שנוצר

        self._move_entries  = {"white": [], "black": []}
        self._seen_moves    = set()

        self._outbound: Queue  = Queue()
        self._login_result: Future = Future()

        self._disconnected_player: str | None = None
        self._disconnected_seconds: int = 0
        self._forfeit_info: dict | None = None
        self._server_gone: bool = False
        self._game_over_info: dict | None = None
        # last login error string for UI feedback
        self._last_login_error: str | None = None

    async def _connect_and_run(self, username: str, password: str, uri: str | None = None) -> None:
        uri = uri or self.uri
        try:
            async with websockets.connect(uri) as ws:
                # send login request
                await ws.send(encode({"type": MsgType.LOGIN, "name": username, "password": password}))

                # main communication loop: regularly attempt to recv (with short timeout)
                # and always drain outbound queue so actions are sent even if no incoming
                # messages arrive for a while.
                while True:
                    # send any queued outbound messages
                    while not self._outbound.empty():
                        msg_to_send = self._outbound.get_nowait()
                        await ws.send(encode(msg_to_send))

                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=0.05)
                    except asyncio.TimeoutError:
                        # no incoming message right now; loop to drain outbound again
                        continue
                    except websockets.exceptions.ConnectionClosed:
                        break

                    msg = decode(raw)
                    msg_type = msg.get("type")

                    # handle login confirmation or error at any time
                    if msg_type == MsgType.OK:
                        if not self._login_result.done():
                            with self._lock:
                                self._my_elo = msg.get("range")
                            self._login_result.set_result(msg)
                        # OK may carry room_id at any point (create_room response)
                        if msg.get("room_id"):
                            with self._lock:
                                self._created_room_id = msg.get("room_id")
                        continue

                    if msg_type == MsgType.ERROR and not self._login_result.done():
                        self._login_result.set_result(msg)
                        continue

                    if msg_type == MsgType.LEADERBOARD:
                        with self._lock:
                            self._leaderboard = msg.get("entries", [])

                    elif msg_type == MsgType.MATCHED:
                        # if server matched us as part of login flow, mark login OK
                        if not self._login_result.done():
                            self._login_result.set_result({"type": MsgType.OK})
                        with self._lock:
                            self._matched_info = msg

                    elif msg_type == MsgType.SNAPSHOT:
                        self._ingest_snapshot(msg)

                    elif msg_type == MsgType.DISCONNECTED:
                        with self._lock:
                            self._disconnected_player  = msg.get("player")
                            self._disconnected_seconds = msg.get("seconds_remaining", 0)

                    elif msg_type == MsgType.RECONNECTED:
                        with self._lock:
                            self._disconnected_player  = None
                            self._disconnected_seconds = 0

                    elif msg_type == MsgType.FORFEIT:
                        with self._lock:
                            self._forfeit_info = {
                                "winner": msg.get("winner"),
                                "reason": msg.get("reason", ""),
                            }

                    elif msg_type == MsgType.GAME_OVER:
                        with self._lock:
                            self._game_over_info = {
                                "winner": msg.get("winner"),
                                "new_elo": msg.get("new_elo"),
                            }

        except Exception as e:
            print(f"[client network error]: {e}")
        finally:
            with self._lock:
                self._server_gone = True
            if not self._login_result.done():
                self._login_result.set_exception(ConnectionError("server disconnected"))

    def _ingest_snapshot(self, snap: dict) -> None:
        now_str = datetime.now().strftime("%H:%M:%S")
        with self._lock:
            self._snapshot = snap
            for m in snap.get("active_moves", []):
                key = (m["from_row"], m["from_col"], m["to_row"], m["to_col"], m["start_time"])
                if key in self._seen_moves:
                    continue
                self._seen_moves.add(key)
                piece_code = m.get("piece_code", "")
                color      = "white" if piece_code.startswith("w") else "black"
                piece_type = piece_code[1] if len(piece_code) > 1 else "?"
                frm = _cell_to_notation(m["from_row"], m["from_col"])
                to  = _cell_to_notation(m["to_row"],   m["to_col"])
                self._move_entries[color].append((now_str, piece_type, frm, to))

    def _run_connection_attempt(self, username: str, password: str, uri: str) -> None:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._connect_and_run(username, password, uri))
        finally:
            loop.close()

    def connect_and_login(self, username: str, password: str) -> dict:
        last_exc = None
        for port in self.ports:
            self.uri = f"ws://{self.host}:{port}"
            self._reset_connection_state()
            self._login_result = Future()
            threading.Thread(
                target=self._run_connection_attempt,
                args=(username, password, self.uri),
                daemon=True,
            ).start()
            try:
                return self._login_result.result(timeout=10)
            except Exception as exc:
                last_exc = exc
                continue

        if last_exc is not None:
            raise last_exc
        raise ConnectionError("could not connect to server")

    def send_action(self, action_type: str, row=None, col=None) -> None:
        msg = {"type": action_type}
        if row is not None: msg["row"] = row
        if col is not None: msg["col"] = col
        self._outbound.put(msg)

    def send_menu_choice(self, choice: str, room_id: str = None, password: str = None) -> None:
        msg = {"type": "menu_choice", "choice": choice}
        if room_id:
            msg["room_id"] = room_id
        if password is not None:
            msg["password"] = password
        self._outbound.put(msg)

    def get_snapshot(self):
        with self._lock:
            return self._snapshot

    def get_matched_info(self):
        with self._lock:
            return self._matched_info

    def get_leaderboard(self):
        with self._lock:
            return list(self._leaderboard)

    def get_move_entries(self, color: str):
        with self._lock:
            return list(self._move_entries[color])

    def get_my_elo(self):
        with self._lock:
            return self._my_elo

    def get_created_room_id(self):
        with self._lock:
            return self._created_room_id

    def get_disconnect_state(self):
        with self._lock:
            return self._disconnected_player, self._disconnected_seconds

    def get_forfeit_info(self):
        with self._lock:
            return self._forfeit_info

    def get_game_over_info(self):
        with self._lock:
            return self._game_over_info

    def clear_game_result(self) -> None:
        with self._lock:
            self._forfeit_info = None
            self._game_over_info = None
            self._matched_info = None
            self._snapshot = None

    def clear_match_state(self) -> None:
        with self._lock:
            self._matched_info = None
            self._snapshot = None

    def _reset_connection_state(self) -> None:
        with self._lock:
            self._snapshot = None
            self._matched_info = None
            self._leaderboard = []
            self._my_elo = None
            self._created_room_id = None
            self._move_entries = {"white": [], "black": []}
            self._seen_moves = set()
            self._disconnected_player = None
            self._disconnected_seconds = 0
            self._forfeit_info = None
            self._server_gone = False
            self._game_over_info = None

    def is_server_gone(self):
        with self._lock:
            return self._server_gone


def _draw_hud(canvas, snap: dict, my_name: str, opp_name: str,
              my_color: str, my_elo, offset_y: int, board_bottom: int) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    cx   = GUI_WINDOW_W // 2

    my_score  = snap.get("white_score", 0) if my_color == "white" else snap.get("black_score", 0)
    opp_score = snap.get("black_score", 0) if my_color == "white" else snap.get("white_score", 0)

    elo_str  = f"  ELO {my_elo}" if my_elo is not None else ""
    my_text  = f"{my_name} ({my_color}){elo_str}   score: {my_score}"
    opp_text = f"{opp_name}   score: {opp_score}"

    (tw, _), _ = cv2.getTextSize(my_text, font, 0.65, 1)
    cv2.putText(canvas, my_text,  (cx - tw // 2, offset_y - 12), font, 0.65, COLOR_SCORE_SELF, 2)

    (tw, _), _ = cv2.getTextSize(opp_text, font, 0.65, 1)
    cv2.putText(canvas, opp_text, (cx - tw // 2, board_bottom + 22), font, 0.65, COLOR_SCORE_OPP, 1)


def _get_menu_option_index_from_click(x: int, y: int, item_x: int, item_w: int, start_y: int, item_h: int, count: int):
    if not (item_x <= x <= item_x + item_w):
        return None

    for index in range(count):
        y0 = start_y + index * item_h
        y1 = y0 + 50
        if y0 <= y <= y1:
            return index
    return None


def draw_main_menu(canvas, menu_state: MenuState):
    canvas[:] = (40, 40, 40)
    font = cv2.FONT_HERSHEY_SIMPLEX

    cv2.putText(canvas, "KUNGFU CHESS - MAIN MENU", (GUI_WINDOW_W // 2 - 220, 80), font, 0.8, (255, 255, 255), 2)

    options = [
        ("View Top 10 Leaders", "leaderboard", (0, 255, 255)),
        ("Get a Match", "match", (0, 255, 0)),
        ("Create a Room", "create_room", (255, 150, 0)),
        ("Join a Room", "join_room", (255, 0, 255)),
    ]

    start_y = 170
    item_h = 70
    item_w = 320
    item_x = GUI_WINDOW_W // 2 - item_w // 2

    for index, (label, value, color) in enumerate(options):
        y = start_y + index * item_h
        selected = index == menu_state.options.index(menu_state.current_value())
        box_color = (255, 255, 255) if selected else (90, 90, 90)
        cv2.rectangle(canvas, (item_x, y), (item_x + item_w, y + 50), box_color, 2)
        cv2.rectangle(canvas, (item_x + 6, y + 6), (item_x + item_w - 6, y + 44), (20, 20, 20), -1)

        if selected:
            cv2.putText(canvas, f"> {label}", (item_x + 20, y + 32), font, 0.55, color, 2)
        else:
            cv2.putText(canvas, label, (item_x + 20, y + 32), font, 0.55, color, 1)

    cv2.putText(canvas, "Click an option, or use arrow keys and Enter.",
                (GUI_WINDOW_W // 2 - 220, 420), font, 0.5, (180, 180, 180), 1)


def _draw_login_screen(canvas, username, password, username_active):
    canvas[:] = (28, 28, 28)
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(canvas, "KUNGFU CHESS LOGIN", (GUI_WINDOW_W // 2 - 180, 120), font, 0.8, (255, 255, 255), 2)
    cv2.putText(canvas, "Username", (GUI_WINDOW_W // 2 - 150, 220), font, 0.6, (220, 220, 220), 1)
    cv2.rectangle(canvas, (GUI_WINDOW_W // 2 - 150, 240), (GUI_WINDOW_W // 2 + 150, 285), (200, 200, 200), 2)
    if username_active:
        cv2.rectangle(canvas, (GUI_WINDOW_W // 2 - 148, 242), (GUI_WINDOW_W // 2 + 148, 283), (0, 255, 255), 2)
    cv2.putText(canvas, username + "_", (GUI_WINDOW_W // 2 - 140, 270), font, 0.55, (255, 255, 255), 1)

    cv2.putText(canvas, "Password", (GUI_WINDOW_W // 2 - 150, 340), font, 0.6, (220, 220, 220), 1)
    cv2.rectangle(canvas, (GUI_WINDOW_W // 2 - 150, 360), (GUI_WINDOW_W // 2 + 150, 405), (200, 200, 200), 2)
    if not username_active:
        cv2.rectangle(canvas, (GUI_WINDOW_W // 2 - 148, 362), (GUI_WINDOW_W // 2 + 148, 403), (0, 255, 255), 2)
    cv2.putText(canvas, "*" * len(password) + "_", (GUI_WINDOW_W // 2 - 140, 390), font, 0.55, (255, 255, 255), 1)
    cv2.putText(canvas, "Tab to switch fields, Enter to login, ESC to exit.",
                (GUI_WINDOW_W // 2 - 240, 510), font, 0.5, (180, 180, 180), 1)

    # Note: the main loop can overlay `client._last_login_error` after calling this


def main():
    client = GameClient()
    cv2.namedWindow("Kungfu Chess")

    current_state = "LOGIN"
    return_state = "MENU"
    username = ""
    password = ""
    username_active = True
    menu_state = MenuState(["leaderboard", "match", "create_room", "join_room"])
    room_input_id = ""
    room_input_pwd = ""
    input_step = "id"

    mouse_click = {"x": None, "y": None, "clicked": False}

    def _handle_mouse(event, x, y, flags, params):
        if event == cv2.EVENT_LBUTTONDOWN:
            params["x"] = x
            params["y"] = y
            params["clicked"] = True

    cv2.setMouseCallback("Kungfu Chess", _handle_mouse, mouse_click)

    try:
        while True:
            if client.is_server_gone():
                break

            canvas = np.zeros((GUI_WINDOW_H, GUI_WINDOW_W, 3), dtype=np.uint8)

            if current_state == "LOGIN":
                _draw_login_screen(canvas, username, password, username_active)
                # overlay last login/connect error if present
                with client._lock:
                    err = getattr(client, "_last_login_error", None)
                if err:
                    cv2.putText(canvas, f"Error: {err}", (GUI_WINDOW_W // 2 - 220, 540),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 60, 255), 1)
                cv2.imshow("Kungfu Chess", canvas)
                key = cv2.waitKey(RENDER_WAIT_MS)

                if key == ESC_KEY:
                    break
                elif key == 9:
                    username_active = not username_active
                elif key in (13, 10):
                    if username and password:
                        try:
                            resp = client.connect_and_login(username, password)
                        except Exception as exc:
                            # keep the app running on transient network/login failures
                            print(f"Could not connect or login: {exc}")
                            password = ""
                            with client._lock:
                                setattr(client, "_last_login_error", str(exc))
                            # allow user to retry
                            continue

                        if resp.get("type") == MsgType.OK:
                            with client._lock:
                                setattr(client, "_last_login_error", None)
                            current_state = "MENU"
                        else:
                            with client._lock:
                                setattr(client, "_last_login_error", resp.get("reason", "login failed"))
                            current_state = "LOGIN"
                            password = ""
                elif key in (8, 127):
                    if username_active:
                        username = username[:-1]
                    else:
                        password = password[:-1]
                elif 32 <= key <= 126:
                    if username_active:
                        username += chr(key)
                    else:
                        password += chr(key)

            elif current_state == "MENU":
                draw_main_menu(canvas, menu_state)
                cv2.imshow("Kungfu Chess", canvas)
                key = cv2.waitKey(RENDER_WAIT_MS)

                if key == ESC_KEY:
                    break
                elif key in (2490368, 63232):
                    menu_state.move_up()
                elif key in (2555904, 63233):
                    menu_state.move_down()
                elif key in (13, 10):
                    selected = menu_state.select()
                    if selected == "leaderboard":
                        current_state = "LEADERBOARD"
                        return_state = "MENU"
                        client.send_menu_choice("leaderboard")
                    elif selected == "match":
                        client.clear_match_state()
                        current_state = "MATCHMAKING"
                        return_state = "MENU"
                        client.send_menu_choice("match")
                    elif selected == "create_room":
                        current_state = "CREATE_ROOM"
                        return_state = "MENU"
                        room_input_pwd = ""
                    elif selected == "join_room":
                        current_state = "JOIN_ROOM"
                        return_state = "MENU"
                        room_input_id = ""
                        room_input_pwd = ""
                        input_step = "id"

                if mouse_click["clicked"]:
                    item_x = GUI_WINDOW_W // 2 - 320 // 2
                    index = _get_menu_option_index_from_click(
                        mouse_click["x"], mouse_click["y"], item_x, 320, 170, 70, len(menu_state.options)
                    )
                    mouse_click["x"] = None
                    mouse_click["y"] = None
                    mouse_click["clicked"] = False
                    if index is not None:
                        menu_state.index = index
                        selected = menu_state.select()
                        if selected == "leaderboard":
                            current_state = "LEADERBOARD"
                            return_state = "MENU"
                            client.send_menu_choice("leaderboard")
                        elif selected == "match":
                            client.clear_match_state()
                            current_state = "MATCHMAKING"
                            return_state = "MENU"
                            client.send_menu_choice("match")
                        elif selected == "create_room":
                            current_state = "CREATE_ROOM"
                            return_state = "MENU"
                            room_input_pwd = ""
                        elif selected == "join_room":
                            current_state = "JOIN_ROOM"
                            return_state = "MENU"
                            room_input_id = ""
                            room_input_pwd = ""
                            input_step = "id"

            elif current_state == "LEADERBOARD":
                lb = client.get_leaderboard()
                draw_leaderboard(canvas, lb, GUI_WINDOW_W // 2 - 110, GUI_WINDOW_H // 2 - 100)
                cv2.putText(canvas, "Press Enter to go back or ESC to exit", (GUI_WINDOW_W // 2 - 150, GUI_WINDOW_H - 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
                cv2.imshow("Kungfu Chess", canvas)

                key = cv2.waitKey(RENDER_WAIT_MS)
                if key == ESC_KEY:
                    current_state = return_state
                    client.send_menu_choice("back")
                elif key in (13, 10):
                    current_state = return_state
                    client.send_menu_choice("back")

            elif current_state == "MATCHMAKING":
                matched = client.get_matched_info()
                if matched:
                    current_state = "GAME"
                    continue

                room_id = client.get_created_room_id()
                text_to_show = f"Room ID: {room_id} (Waiting for player...)" if room_id else "Waiting for opponent..."

                cv2.putText(canvas, text_to_show, (GUI_WINDOW_W // 2 - 220, GUI_WINDOW_H // 2 - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.putText(canvas, "Press ESC to return to Menu", (GUI_WINDOW_W // 2 - 130, GUI_WINDOW_H - 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
                cv2.imshow("Kungfu Chess", canvas)

                key = cv2.waitKey(RENDER_WAIT_MS)
                if key == ESC_KEY:
                    current_state = return_state
                    client.send_menu_choice("back")

            elif current_state == "CREATE_ROOM":
                cv2.putText(canvas, "Enter Room Password and press Enter:", (GUI_WINDOW_W // 2 - 180, GUI_WINDOW_H // 2 - 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                cv2.putText(canvas, room_input_pwd + "_", (GUI_WINDOW_W // 2 - 80, GUI_WINDOW_H // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 150, 0), 2)
                cv2.putText(canvas, "Press ESC to return to Menu", (GUI_WINDOW_W // 2 - 130, GUI_WINDOW_H - 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
                cv2.imshow("Kungfu Chess", canvas)

                key = cv2.waitKey(RENDER_WAIT_MS)
                if key == ESC_KEY:
                    current_state = return_state
                elif key == 13:
                    client.send_menu_choice("create_room", password=room_input_pwd)
                    current_state = "MATCHMAKING"
                elif key in (8, 127):
                    room_input_pwd = room_input_pwd[:-1]
                elif 32 <= key <= 126:
                    room_input_pwd += chr(key)

            elif current_state == "JOIN_ROOM":
                if input_step == "id":
                    cv2.putText(canvas, "Enter Room ID and press Enter:", (GUI_WINDOW_W // 2 - 160, GUI_WINDOW_H // 2 - 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                    cv2.putText(canvas, room_input_id + "_", (GUI_WINDOW_W // 2 - 80, GUI_WINDOW_H // 2),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                else:
                    cv2.putText(canvas, "Enter Room Password and press Enter:", (GUI_WINDOW_W // 2 - 180, GUI_WINDOW_H // 2 - 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                    cv2.putText(canvas, room_input_pwd + "_", (GUI_WINDOW_W // 2 - 80, GUI_WINDOW_H // 2),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

                cv2.putText(canvas, "Press ESC to return to Menu", (GUI_WINDOW_W // 2 - 130, GUI_WINDOW_H - 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
                cv2.imshow("Kungfu Chess", canvas)

                key = cv2.waitKey(RENDER_WAIT_MS)
                if key == ESC_KEY:
                    current_state = return_state
                    room_input_id = ""
                    room_input_pwd = ""
                    input_step = "id"
                elif key == 13:
                    if input_step == "id" and room_input_id:
                        input_step = "pwd"
                    elif input_step == "pwd":
                        client.send_menu_choice("join_room", room_id=room_input_id, password=room_input_pwd)
                        current_state = "MATCHMAKING"
                elif key in (8, 127):
                    if input_step == "id":
                        room_input_id = room_input_id[:-1]
                    else:
                        room_input_pwd = room_input_pwd[:-1]
                elif 32 <= key <= 126:
                    if input_step == "id":
                        room_input_id += chr(key)
                    else:
                        room_input_pwd += chr(key)

            elif current_state == "GAME":
                pieces_dir = os.path.abspath(os.path.join(resolve_pieces_dir(__file__), PIECES_SET))
                renderer = AnimatedRenderer(
                    resolve_board_image(__file__), pieces_dir,
                    GUI_WINDOW_W, GUI_WINDOW_H, GUI_BOARD_SIZE,
                )

                matched = client.get_matched_info()
                my_color = matched.get("color", "white") if matched else "white"
                opp_name = matched.get("opponent", "?") if matched else "Opponent"
                flipped = (my_color == "black")

                controller = GUIController(renderer, client, flipped=flipped)
                cv2.setMouseCallback("Kungfu Chess", controller.get_mouse_callback())

                offset_y = (GUI_WINDOW_H - GUI_BOARD_SIZE) // 2
                board_bottom = offset_y + GUI_BOARD_SIZE
                board_x = (GUI_WINDOW_W - GUI_BOARD_SIZE) // 2

                my_log_color = (220, 220, 220) if my_color == "white" else (120, 120, 120)
                opp_log_color = (120, 120, 120) if my_color == "white" else (220, 220, 220)
                opp_color = "black" if my_color == "white" else "white"

                game_running = True
                while game_running:
                    if client.is_server_gone():
                        current_state = "MENU"
                        break

                    forfeit = client.get_forfeit_info()
                    game_over = client.get_game_over_info()
                    result = forfeit or game_over

                    if result:
                        snap = client.get_snapshot()
                        canvas = renderer.render(snap, selected=None, flipped=flipped) if snap else \
                                 np.zeros((GUI_WINDOW_H, GUI_WINDOW_W, 3), dtype=np.uint8)
                        winner = result["winner"]
                        outcome = "You win!" if winner == username else f"{winner} wins!"

                        cv2.putText(canvas, outcome, (GUI_WINDOW_W // 2 - 80, GUI_WINDOW_H // 2),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                        cv2.imshow("Kungfu Chess", canvas)
                        cv2.waitKey(2000)
                        client.clear_game_result()
                        # Reset mouse callback back to menu handler
                        cv2.setMouseCallback("Kungfu Chess", _handle_mouse, mouse_click)
                        current_state = "MENU"
                        game_running = False
                        break

                    disc_player, disc_secs = client.get_disconnect_state()
                    if disc_player:
                        canvas = np.zeros((GUI_WINDOW_H, GUI_WINDOW_W, 3), dtype=np.uint8)
                        cv2.putText(canvas, f"{disc_player} disconnected... {disc_secs}s", (50, 100),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                        cv2.imshow("Kungfu Chess", canvas)
                        cv2.waitKey(RENDER_WAIT_MS)
                        continue

                    snap = client.get_snapshot()
                    if snap:
                        canvas = renderer.render(snap, selected=controller.selected, flipped=flipped)
                        draw_board_labels(canvas, board_x, offset_y, GUI_BOARD_SIZE, flipped=flipped)
                        _draw_hud(canvas, snap, username, opp_name, my_color,
                                  client.get_my_elo(), offset_y, board_bottom)
                        draw_move_log(canvas, client.get_move_entries(my_color),
                                      10, offset_y, f"{username} ({my_color}) moves", my_log_color)
                        draw_move_log(canvas, client.get_move_entries(opp_color),
                                      GUI_WINDOW_W - PANEL_W - 10, offset_y,
                                      f"{opp_name} ({opp_color}) moves", opp_log_color)
                        cv2.imshow("Kungfu Chess", canvas)

                    key = cv2.waitKey(RENDER_WAIT_MS)
                    if key == ESC_KEY:
                        cv2.setMouseCallback("Kungfu Chess", _handle_mouse, mouse_click)
                        current_state = "MENU"
                        game_running = False
                        break

    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()