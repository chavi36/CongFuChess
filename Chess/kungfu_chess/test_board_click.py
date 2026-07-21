import os
import cv2
import numpy as np
from img import Img
from application.path_utils import resolve_project_path, resolve_pieces_dir, resolve_board_image

# ── CONFIG ───────────────────────────────────────────────────────────────────
WINDOW_W, WINDOW_H = 900, 900
BOARD_SIZE = 700        # board will be resized to this (square)
MARKER_PATH = os.path.join(resolve_pieces_dir(__file__), "pieces1", "QW", "states", "idle", "sprites", "1.png")
# ─────────────────────────────────────────────────────────────────────────────

CELL_SIZE   = BOARD_SIZE // 8
OFFSET_X    = (WINDOW_W - BOARD_SIZE) // 2
OFFSET_Y    = (WINDOW_H - BOARD_SIZE) // 2


def pixel_to_cell(px, py):
    col = (px - OFFSET_X) // CELL_SIZE
    row = (py - OFFSET_Y) // CELL_SIZE
    return row, col


def in_bounds(row, col):
    return 0 <= row < 8 and 0 <= col < 8


def main():
    board = Img().read(resolve_board_image(__file__), size=(BOARD_SIZE, BOARD_SIZE))
    marker = Img().read(MARKER_PATH, size=(CELL_SIZE, CELL_SIZE))

    canvas = np.zeros((WINDOW_H, WINDOW_W, 3), dtype=np.uint8)
    board.draw_on_np(canvas, OFFSET_X, OFFSET_Y)

    base = canvas.copy()

    def on_mouse(event, x, y, flags, param):
        nonlocal canvas
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        row, col = pixel_to_cell(x, y)
        if in_bounds(row, col):
            print(f"cell ({row}, {col})")
            canvas = base.copy()
            px = OFFSET_X + col * CELL_SIZE
            py = OFFSET_Y + row * CELL_SIZE
            marker.draw_on_np(canvas, px, py)

    cv2.namedWindow("Board Test")
    cv2.setMouseCallback("Board Test", on_mouse)

    while True:
        cv2.imshow("Board Test", canvas)
        if cv2.waitKey(30) & 0xFF in (27, ord('q')):
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
