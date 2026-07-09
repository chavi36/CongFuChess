"""
Rule engine for Kungfu Chess.
Combines per-piece rules into a single is_valid_move / get_move_distance API
consumed by the GameEngine.
"""

from kungfu_chess.model.board import BoardInterface
from kungfu_chess.model.config import EMPTY_SQUARE
from kungfu_chess.rules.piece_rules import PieceRules


class RuleEngine:
    """Validates moves and computes distances for the engine."""

    def __init__(self, board: BoardInterface):
        self.board = board
        self._piece_rules = PieceRules(board)

    def is_valid_move(self, from_row: int, from_col: int,
                      to_row: int, to_col: int) -> bool:
        piece_code = self.board.get_piece(from_row, from_col)
        if not piece_code or piece_code == EMPTY_SQUARE:
            return False

        piece_color = piece_code[0]
        piece_type = piece_code[1]

        target = self.board.get_piece(to_row, to_col)
        if target != EMPTY_SQUARE and target[0] == piece_color:
            return False

        if piece_type == 'P':
            return self._piece_rules.is_valid_pawn_move(
                from_row, from_col, to_row, to_col, piece_color)
        if piece_type == 'N':
            return self._piece_rules.is_valid_knight_move(
                from_row, from_col, to_row, to_col)
        if piece_type in 'KQRB':
            return self._piece_rules.is_valid_sliding_move(
                from_row, from_col, to_row, to_col, piece_type)

        return False

    def get_move_distance(self, from_row: int, from_col: int,
                          to_row: int, to_col: int) -> int:
        return max(abs(to_row - from_row), abs(to_col - from_col))
