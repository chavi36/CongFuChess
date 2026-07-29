import numpy as np
from Core.img import Img
from Core.model.board import BoardInterface
from Core.model.config import EMPTY_SQUARE, BOARD_COLS, BOARD_ROWS
import os


def _to_sprite_code(engine_code, pieces_dir=None):
    """Resolve engine code to the sprite folder that actually exists in pieces_dir."""
    explicit_map = {
        "wK": "KW",
        "wQ": "QW",
        "wR": "RW",
        "wB": "BW",
        "wN": "NW",
        "wP": "PW",
        "bK": "KB",
        "bQ": "QB",
        "bR": "RB",
        "bB": "BB",
        "bN": "NB",
        "bP": "PB",
        "KW": "KW",
        "QW": "QW",
        "RW": "RW",
        "BW": "BW",
        "NW": "NW",
        "PW": "PW",
        "KB": "KB",
        "QB": "QB",
        "RB": "RB",
        "BB": "BB",
        "NB": "NB",
        "PB": "PB",
    }
    if engine_code in explicit_map:
        return explicit_map[engine_code]

    color, piece = engine_code[0], engine_code[1]
    base_piece = piece.upper()
    candidates = [
        engine_code,
        base_piece + ("W" if color == "w" else "B"),
        base_piece + color.upper(),
        base_piece,
    ]

    if pieces_dir:
        for name in candidates:
            if os.path.isdir(os.path.join(pieces_dir, name)):
                return name

        for name in candidates:
            if os.path.isdir(os.path.join(pieces_dir, "pieces4", name)):
                return os.path.join("pieces4", name)

    return candidates[0]


class BoardRenderer:
    def __init__(self, board_path, pieces_dir, window_w, window_h, board_size):
        self.pieces_dir = pieces_dir
        self.window_w   = window_w
        self.window_h   = window_h
        self.board_size = board_size
        self.cell_size  = board_size // 8
        self.offset_x   = (window_w - board_size) // 2
        self.offset_y   = (window_h - board_size) // 2
        self._board_img = Img().read(board_path, size=(board_size, board_size))
        self._sprite_cache  = {}
        self._code_cache    = {}  # engine_code -> resolved folder name
        self._cached_canvas = None
        self._last_snapshot = None

    def _resolve_code(self, engine_code):
        return self._code_cache.setdefault(engine_code, _to_sprite_code(engine_code, self.pieces_dir))

    def _piece_sprite(self, engine_code):
        sprite_code = self._resolve_code(engine_code)
        if sprite_code not in self._sprite_cache:
            path = os.path.join(self.pieces_dir, sprite_code, "states", "idle", "sprites", "1.png")
            if not os.path.isfile(path):
                fallback = os.path.join(self.pieces_dir, "pieces4", sprite_code, "states", "idle", "sprites", "1.png")
                if os.path.isfile(fallback):
                    path = fallback
            self._sprite_cache[sprite_code] = Img().read(path, size=(self.cell_size, self.cell_size))
        return self._sprite_cache[sprite_code]

    def _board_snapshot(self, board: BoardInterface):
        return tuple(board.get_piece(r, c)
                     for r in range(board.get_height())
                     for c in range(board.get_width()))

    def render(self, board):
        snapshot = self._board_snapshot(board)
        if snapshot == self._last_snapshot:
            return self._cached_canvas
        canvas = np.zeros((self.window_h, self.window_w, 3), dtype=np.uint8)
        self._board_img.draw_on_np(canvas, self.offset_x, self.offset_y)
        for r in range(board.get_height()):
            for c in range(board.get_width()):
                piece = board.get_piece(r, c)
                if piece == EMPTY_SQUARE:
                    continue
                try:
                    sprite = self._piece_sprite(piece)
                    px = self.offset_x + c * self.cell_size
                    py = self.offset_y + r * self.cell_size
                    sprite.draw_on_np(canvas, px, py)
                except FileNotFoundError:
                    pass
        self._cached_canvas = canvas
        self._last_snapshot = snapshot
        return canvas
#אולי פה עדיף שאני אשאיר את הלוגיקה הזאת לכל החלק של הלוגיקה?
# אני חשבתי שכדאי פה בגלל שאני רוצה שהפיקסלים בשלב הזה יהיו כמו גודל תא בלוח
    def pixel_to_cell(self, px, py):
        col = (px - self.offset_x) // self.cell_size
        row = (py - self.offset_y) // self.cell_size
        return row, col

    def in_bounds(self, row, col):
        return 0 <= row < BOARD_ROWS and 0 <= col < BOARD_COLS
