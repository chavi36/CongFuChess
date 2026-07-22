import cv2
import numpy as np
from Core.realtime.move_observer import MoveObserver

PANEL_W     = 250
PANEL_H     = 700
ROW_H       = 18
HEADER_H    = 40   # title row + column labels row
MAX_VISIBLE = (PANEL_H - HEADER_H) // ROW_H

# column x-offsets inside the panel
COL_TIME  = 6
COL_PIECE = 115
COL_MOVE  = 145


def draw_board_labels(canvas: np.ndarray,
                      board_x: int, board_y: int,
                      board_size: int) -> None:
    """Draw a-h column letters and 1-8 row numbers around the board."""
    cell = board_size // 8
    color = (180, 180, 180)
    font  = cv2.FONT_HERSHEY_SIMPLEX

    for col in range(8):
        letter = chr(ord('a') + col)
        cx = board_x + col * cell + cell // 2 - 5
        # below the board
        cv2.putText(canvas, letter, (cx, board_y + board_size + 18), font, 0.45, color, 1)
        # above the board
        cv2.putText(canvas, letter, (cx, board_y - 6), font, 0.45, color, 1)

    for row in range(8):
        number = str(8 - row)
        ry = board_y + row * cell + cell // 2 + 5
        # left of the board
        cv2.putText(canvas, number, (board_x - 18, ry), font, 0.45, color, 1)
        # right of the board
        cv2.putText(canvas, number, (board_x + board_size + 6, ry), font, 0.45, color, 1)


def draw_move_log(canvas: np.ndarray,
                  observer: MoveObserver,
                  x: int, y: int,
                  title: str,
                  color_bgr: tuple) -> None:
    # background + border
    cv2.rectangle(canvas, (x, y), (x + PANEL_W, y + PANEL_H), (30, 30, 30), -1)
    cv2.rectangle(canvas, (x, y), (x + PANEL_W, y + PANEL_H), color_bgr, 1)

    # title
    cv2.putText(canvas, title, (x + 6, y + 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_bgr, 1)

    # column headers
    header_y = y + 32
    cv2.putText(canvas, "at",      (x + COL_TIME,  header_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color_bgr, 1)
    cv2.putText(canvas, "pc",      (x + COL_PIECE, header_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color_bgr, 1)
    cv2.putText(canvas, "from-to", (x + COL_MOVE,  header_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color_bgr, 1)
    cv2.line(canvas, (x, y + HEADER_H), (x + PANEL_W, y + HEADER_H), color_bgr, 1)

    # rows — most recent at top
    entries = observer.entries[-MAX_VISIBLE:]
    for i, (wall_time, piece_type, frm, to) in enumerate(reversed(entries)):
        row_y = y + HEADER_H + i * ROW_H + ROW_H - 4
        cv2.putText(canvas, wall_time,      (x + COL_TIME,  row_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 200, 200), 1)
        cv2.putText(canvas, piece_type,     (x + COL_PIECE, row_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 200, 200), 1)
        cv2.putText(canvas, f"{frm}-{to}",  (x + COL_MOVE,  row_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 200, 200), 1)
