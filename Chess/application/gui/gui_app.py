import os
import cv2
from application.bridge.game_session import GameSession
from application.gui.animated_renderer import AnimatedRenderer
from application.gui.gui_controller import GUIController
from application.gui.move_log_panel import draw_move_log, draw_board_labels, PANEL_W
from kungfu_chess.model.config import PieceColor
from kungfu_chess.model.player import Player
from application.path_utils import resolve_project_path, resolve_pieces_dir, resolve_board_image

# ── CONFIG ───────────────────────────────────────────────────────────────────
WINDOW_W   = 1300
WINDOW_H   = 900
BOARD_SIZE = 700
TICK_MS    = 30
BASE_DIR   = resolve_project_path(__file__)
BOARD_IMG  = resolve_board_image(__file__)
PIECES_SET = "pieces4"
PIECES_DIR = os.path.join(resolve_pieces_dir(__file__), PIECES_SET)
BOARD_CSV  = os.path.join(resolve_pieces_dir(__file__), "pieces1", "board.csv")
WHITE_PLAYER = Player(name="shloimy", color=PieceColor.WHITE)
BLACK_PLAYER = Player(name="chavi",   color=PieceColor.BLACK)
# ─────────────────────────────────────────────────────────────────────────────



def main():
    import time

    renderer   = AnimatedRenderer(BOARD_IMG, PIECES_DIR, WINDOW_W, WINDOW_H, BOARD_SIZE)
    cv2.namedWindow("Kungfu Chess")

    def make_session():
        renderer._capture_flashes.clear()
        session    = GameSession(BOARD_CSV, WHITE_PLAYER, BLACK_PLAYER, renderer)
        controller = GUIController(renderer, session)
        cv2.setMouseCallback("Kungfu Chess", controller.get_mouse_callback())
        return session, controller

    session, controller = make_session()

    last_tick    = time.monotonic()
    offset_y     = (WINDOW_H - BOARD_SIZE) // 2
    board_bottom = offset_y + BOARD_SIZE
    board_x      = (WINDOW_W - BOARD_SIZE) // 2

    while True:
        now     = time.monotonic()
        elapsed = int((now - last_tick) * 1000)
        if elapsed >= TICK_MS:
            session.tick(elapsed)
            last_tick = now

        canvas = renderer.render(session.get_render_snapshot(), selected=controller.selected)
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
        draw_move_log(canvas, session.white_observer, 10, panel_y, f"{WHITE_PLAYER.name} moves", (220, 220, 220))
        draw_move_log(canvas, session.black_observer, WINDOW_W - PANEL_W - 10, panel_y, f"{BLACK_PLAYER.name} moves", (120, 120, 120))

        cv2.imshow("Kungfu Chess", canvas)
        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            break
        if session.is_over() and key != 255:
            session, controller = make_session()
            last_tick = time.monotonic()

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
