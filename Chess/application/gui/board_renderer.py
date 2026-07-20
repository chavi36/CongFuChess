import numpy as np
from kungfu_chess.img import Img

import os

def _to_sprite_code(engine_code, pieces_dir=None):
    """Resolve engine code to whichever folder name actually exists in pieces_dir."""
    color, piece = engine_code[0], engine_code[1]
    candidates = [
        engine_code,                             # wK  (pieces3)
        piece + ('W' if color == 'w' else 'B'),  # KW  (pieces2)
        piece + color.upper(),                   # KB  (any other variant)
    ]
    if pieces_dir:
        for name in candidates:
            if os.path.isdir(os.path.join(pieces_dir, name)):
                return name
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
            path = f"{self.pieces_dir}/{sprite_code}/states/idle/sprites/1.png"
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
                if piece == '.':
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
        return 0 <= row < 8 and 0 <= col < 8
