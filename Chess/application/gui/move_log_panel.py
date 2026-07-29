import cv2
import numpy as np
from Core.model.config import BOARD_COLS, BOARD_ROWS

PANEL_W     = 250
PANEL_H     = 700
ROW_H       = 18
HEADER_H    = 40
MAX_VISIBLE = (PANEL_H - HEADER_H) // ROW_H

COL_TIME  = 6
COL_PIECE = 115
COL_MOVE  = 145

LEADERBOARD_W   = 220
LEADERBOARD_ROW = 22


def draw_board_labels(canvas: np.ndarray,
                      board_x: int, board_y: int,
                      board_size: int,
                      flipped: bool = False) -> None:
    """Draw a-h / 1-8 labels around the board. Reverses order when flipped."""
    cell  = board_size // 8
    color = (180, 180, 180)
    font  = cv2.FONT_HERSHEY_SIMPLEX

    for col in range(BOARD_COLS):
        display_col = (BOARD_COLS - 1 - col) if flipped else col
        letter = chr(ord('a') + display_col)
        cx = board_x + col * cell + cell // 2 - 5
        cv2.putText(canvas, letter, (cx, board_y + board_size + 18), font, 0.45, color, 1)
        cv2.putText(canvas, letter, (cx, board_y - 6),               font, 0.45, color, 1)

    for row in range(BOARD_ROWS):
        display_row = row if flipped else (BOARD_ROWS - 1 - row)
        number = str(display_row + 1)
        ry = board_y + row * cell + cell // 2 + 5
        cv2.putText(canvas, number, (board_x - 18,               ry), font, 0.45, color, 1)
        cv2.putText(canvas, number, (board_x + board_size + 6,   ry), font, 0.45, color, 1)


def draw_move_log(canvas: np.ndarray,
                  entries: list,
                  x: int, y: int,
                  title: str,
                  color_bgr: tuple) -> None:
    """
    Draw a move-log panel from a plain list of (wall_time, piece_type, from, to) tuples.
    Works for both local (MoveObserver.entries) and network (client-side accumulated list).
    """
    cv2.rectangle(canvas, (x, y), (x + PANEL_W, y + PANEL_H), (30, 30, 30), -1)
    cv2.rectangle(canvas, (x, y), (x + PANEL_W, y + PANEL_H), color_bgr, 1)

    cv2.putText(canvas, title, (x + 6, y + 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_bgr, 1)

    header_y = y + 32
    cv2.putText(canvas, "at",      (x + COL_TIME,  header_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color_bgr, 1)
    cv2.putText(canvas, "pc",      (x + COL_PIECE, header_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color_bgr, 1)
    cv2.putText(canvas, "from-to", (x + COL_MOVE,  header_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color_bgr, 1)
    cv2.line(canvas, (x, y + HEADER_H), (x + PANEL_W, y + HEADER_H), color_bgr, 1)

    visible = entries[-MAX_VISIBLE:]
    for i, (wall_time, piece_type, frm, to) in enumerate(reversed(visible)):
        row_y = y + HEADER_H + i * ROW_H + ROW_H - 4
        cv2.putText(canvas, wall_time,     (x + COL_TIME,  row_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 200, 200), 1)
        cv2.putText(canvas, piece_type,    (x + COL_PIECE, row_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 200, 200), 1)
        cv2.putText(canvas, f"{frm}-{to}", (x + COL_MOVE,  row_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 200, 200), 1)


def draw_leaderboard(canvas: np.ndarray,
                     entries: list,
                     x: int, y: int) -> None:
    """
    Draw a leaderboard panel.
    entries: list of {"name": str, "range": int} dicts, already sorted best-first.
    """
    h = LEADERBOARD_ROW * (len(entries) + 2) + 10
    cv2.rectangle(canvas, (x, y), (x + LEADERBOARD_W, y + h), (30, 30, 30), -1)
    cv2.rectangle(canvas, (x, y), (x + LEADERBOARD_W, y + h), (180, 150, 50), 1)

    cv2.putText(canvas, "Top Players", (x + 6, y + 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 150, 50), 1)
    cv2.line(canvas, (x, y + LEADERBOARD_ROW + 4), (x + LEADERBOARD_W, y + LEADERBOARD_ROW + 4),
             (180, 150, 50), 1)

    for i, entry in enumerate(entries):
        row_y = y + (i + 2) * LEADERBOARD_ROW + 4
        text  = f"{i + 1}. {entry['name']}  {entry['range']}"
        cv2.putText(canvas, text, (x + 6, row_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (210, 210, 210), 1)
