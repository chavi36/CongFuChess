import os
import csv
import cv2
from kungfu_chess.gui.animated_renderer import AnimatedRenderer
from kungfu_chess.gui.gui_controller import GUIController
from kungfu_chess.gui.move_log_panel import draw_move_log, draw_board_labels, PANEL_W
from kungfu_chess.model.board import TextBoard
from kungfu_chess.model.config import PieceColor
from kungfu_chess.model.player import Player
from kungfu_chess.realtime.move_observer import MoveObserver
from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.input.controller import CommandExecutor

# ── CONFIG ───────────────────────────────────────────────────────────────────
WINDOW_W   = 1300
WINDOW_H   = 900
BOARD_SIZE = 700
TICK_MS    = 30
BASE_DIR   = os.path.dirname(os.path.dirname(__file__))  # kungfu_chess/
BOARD_IMG  = os.path.join(BASE_DIR, "board.png")
PIECES_SET = "pieces4"  # change this to switch sprite set: pieces1, pieces2, pieces3, pieces4
PIECES_DIR = os.path.join(BASE_DIR, "anotations", PIECES_SET)
BOARD_CSV  = os.path.join(BASE_DIR, "anotations", "pieces1", "board.csv")
WHITE_PLAYER = Player(name="shloimy", color=PieceColor.WHITE)
BLACK_PLAYER = Player(name="chavi",   color=PieceColor.BLACK)
# ─────────────────────────────────────────────────────────────────────────────


def load_board_from_csv(path):
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    # convert CSV codes (e.g. 'KW') to engine codes (e.g. 'wK')
    # בעצם את הההמרה הזאת יכול להיות שלא צריך לעשות גם פה כי ממילא ברינדור הוא עושה את ההמרה
    def convert(code):
        if not code:
            return '.'
        piece, color = code[0], code[1]
        return ('w' if color == 'W' else 'b') + piece
    return [[convert(cell) for cell in row] for row in rows]


def _build_engine(board_csv, players):
    board_data = load_board_from_csv(board_csv)
    board      = TextBoard(board_data)
    engine     = GameEngine(board, players=players)
    return engine


def main():
    import time

    renderer   = AnimatedRenderer(BOARD_IMG, PIECES_DIR, WINDOW_W, WINDOW_H, BOARD_SIZE)
    cv2.namedWindow("Kungfu Chess")

    def make_session():
        WHITE_PLAYER.score = 0
        BLACK_PLAYER.score = 0
        white_observer     = MoveObserver(color='w')
        black_observer     = MoveObserver(color='b')
        engine             = _build_engine(BOARD_CSV, [WHITE_PLAYER, BLACK_PLAYER])
        engine.arbiter.set_observers({'w': white_observer, 'b': black_observer})
        engine.arbiter.set_renderer(renderer)
        renderer._capture_flashes.clear()
        executor   = CommandExecutor(engine)
        controller = GUIController(renderer, executor)
        cv2.setMouseCallback("Kungfu Chess", controller.get_mouse_callback())
        return engine, white_observer, black_observer, controller

    engine, white_observer, black_observer, controller = make_session()

    last_tick    = time.monotonic()
    offset_y     = (WINDOW_H - BOARD_SIZE) // 2
    board_bottom = offset_y + BOARD_SIZE
    board_x      = (WINDOW_W - BOARD_SIZE) // 2
    winner       = None

    while True:
        now     = time.monotonic()
        elapsed = int((now - last_tick) * 1000)
        if elapsed >= TICK_MS:
            engine.advance_time(elapsed)
            last_tick = now

        # determine winner when game ends
        if engine.state.is_game_over() and winner is None:
            if WHITE_PLAYER.score >= BLACK_PLAYER.score:
                winner = WHITE_PLAYER.name
            else:
                winner = BLACK_PLAYER.name

        canvas = renderer.render(engine, selected=controller.selected, winner=winner)

        # player name + score
        white_text = f"{WHITE_PLAYER.name}  {WHITE_PLAYER.score}"
        (tw, _), _ = cv2.getTextSize(white_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
        cv2.putText(canvas, white_text, ((WINDOW_W - tw) // 2, offset_y - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        black_text = f"{BLACK_PLAYER.name}  {BLACK_PLAYER.score}"
        (tw, _), _ = cv2.getTextSize(black_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
        cv2.putText(canvas, black_text, ((WINDOW_W - tw) // 2, board_bottom + 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (180, 180, 180), 2)

        # board coordinate labels
        draw_board_labels(canvas, board_x, offset_y, BOARD_SIZE)

        # move log panels
        panel_y = offset_y
        draw_move_log(canvas, white_observer, 10, panel_y, f"{WHITE_PLAYER.name} moves", (220, 220, 220))
        draw_move_log(canvas, black_observer, WINDOW_W - PANEL_W - 10, panel_y, f"{BLACK_PLAYER.name} moves", (120, 120, 120))

        cv2.imshow("Kungfu Chess", canvas)
        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            break
        if engine.state.is_game_over() and key != 255:
            engine, white_observer, black_observer, controller = make_session()
            winner    = None
            last_tick = time.monotonic()

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
