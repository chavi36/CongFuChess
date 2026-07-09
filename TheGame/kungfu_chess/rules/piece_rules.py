"""
Piece movement rules for Kungfu Chess.
Contains per-piece-type validation helpers used by RuleEngine.
"""

from kungfu_chess.model.board import BoardInterface
from kungfu_chess.model.config import EMPTY_SQUARE, PAWN_CONFIG


class PieceRules:
    """Pure movement-geometry checks — no board state side effects."""

    def __init__(self, board: BoardInterface):
        self.board = board

    def is_valid_pawn_move(self, from_row: int, from_col: int,
                           to_row: int, to_col: int, color: str) -> bool:
        config = PAWN_CONFIG['white' if color == 'w' else 'black']
        direction = config['direction']
        start_row = config['start_row']
        dr, dc = to_row - from_row, to_col - from_col

        if dc == 0:
            if dr == direction:
                return self.board.is_empty(to_row, to_col)
            if dr == 2 * direction and from_row == start_row:
                mid_row = from_row + direction
                return (self.board.is_empty(mid_row, from_col) and
                        self.board.is_empty(to_row, to_col))
            return False
        if abs(dc) == 1 and dr == direction:
            return not self.board.is_empty(to_row, to_col)
        return False

    def is_valid_knight_move(self, from_row: int, from_col: int,
                             to_row: int, to_col: int) -> bool:
        dr = abs(to_row - from_row)
        dc = abs(to_col - from_col)
        return (dr == 1 and dc == 2) or (dr == 2 and dc == 1)

    def is_valid_sliding_move(self, from_row: int, from_col: int,
                              to_row: int, to_col: int,
                              piece_type: str) -> bool:
        dr = to_row - from_row
        dc = to_col - from_col
        if dr == 0 and dc == 0:
            return False
        if piece_type == 'K':
            return abs(dr) <= 1 and abs(dc) <= 1
        if piece_type == 'R' and dr != 0 and dc != 0:
            return False
        if piece_type == 'B' and abs(dr) != abs(dc):
            return False
        if piece_type == 'Q' and dr != 0 and dc != 0 and abs(dr) != abs(dc):
            return False
        return self._is_path_clear(from_row, from_col, to_row, to_col)

    def _is_path_clear(self, from_row: int, from_col: int,
                       to_row: int, to_col: int) -> bool:
        dr = 0 if from_row == to_row else (1 if to_row > from_row else -1)
        dc = 0 if from_col == to_col else (1 if to_col > from_col else -1)
        curr_row, curr_col = from_row + dr, from_col + dc
        while (curr_row, curr_col) != (to_row, to_col):
            if not self.board.is_empty(curr_row, curr_col):
                return False
            curr_row += dr
            curr_col += dc
        return True
