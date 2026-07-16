import os
import csv
import cv2
from kungfu_chess.gui.animated_renderer import AnimatedRenderer
from kungfu_chess.gui.gui_controller import GUIController
from kungfu_chess.model.board import TextBoard
from kungfu_chess.model.config import PieceColor
from kungfu_chess.model.player import Player
from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.input.controller import CommandExecutor

# ── CONFIG ───────────────────────────────────────────────────────────────────
WINDOW_W   = 900
WINDOW_H   = 900
BOARD_SIZE = 700
TICK_MS    = 30
BASE_DIR   = os.path.dirname(os.path.dirname(__file__))  # kungfu_chess/
BOARD_IMG  = os.path.join(BASE_DIR, "board.png")
PIECES_DIR = os.path.join(BASE_DIR, "anotations", "pieces3")
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


def main():
    board_data = load_board_from_csv(BOARD_CSV)
    board      = TextBoard(board_data)
    engine     = GameEngine(board, players=[WHITE_PLAYER, BLACK_PLAYER])
    executor   = CommandExecutor(engine)
    renderer   = AnimatedRenderer(BOARD_IMG, PIECES_DIR, WINDOW_W, WINDOW_H, BOARD_SIZE)
    controller = GUIController(renderer, executor)

    cv2.namedWindow("Kungfu Chess")
    cv2.setMouseCallback("Kungfu Chess", controller.get_mouse_callback())

    import time
    last_tick = time.monotonic()

    offset_y = (WINDOW_H - BOARD_SIZE) // 2  # 100
    board_bottom = offset_y + BOARD_SIZE        # 800

    while True:
        now = time.monotonic()
        elapsed = int((now - last_tick) * 1000)
        if elapsed >= TICK_MS:
            engine.advance_time(elapsed)
            last_tick = now
        canvas = renderer.render(engine)

        # White player — above the board (centered)
        white_text = f"{WHITE_PLAYER.name}  {WHITE_PLAYER.score}"
        (tw, th), _ = cv2.getTextSize(white_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
        cv2.putText(canvas, white_text, ((WINDOW_W - tw) // 2, offset_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        # Black player — below the board (centered)
        black_text = f"{BLACK_PLAYER.name}  {BLACK_PLAYER.score}"
        (tw, th), _ = cv2.getTextSize(black_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
        cv2.putText(canvas, black_text, ((WINDOW_W - tw) // 2, board_bottom + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (180, 180, 180), 2)

        cv2.imshow("Kungfu Chess", canvas)
        if cv2.waitKey(1) & 0xFF in (27, ord('q')):
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
