import unittest
from kungfu_chess.model.board import TextBoard
from kungfu_chess.rules.piece_rules import PieceRules


def _empty(size=8):
    return [['.' for _ in range(size)] for _ in range(size)]


class TestPieceRules(unittest.TestCase):
    # ---- pawn ----
    def test_pawn_forward_one(self):
        data = _empty()
        data[4][4] = 'wP'
        rules = PieceRules(TextBoard(data))
        self.assertTrue(rules.is_valid_pawn_move(4, 4, 3, 4, 'w'))

    def test_pawn_forward_blocked(self):
        data = _empty()
        data[4][4] = 'wP'
        data[3][4] = 'bP'
        rules = PieceRules(TextBoard(data))
        self.assertFalse(rules.is_valid_pawn_move(4, 4, 3, 4, 'w'))

    def test_pawn_double_from_start(self):
        data = _empty()
        data[6][2] = 'wP'
        rules = PieceRules(TextBoard(data))
        self.assertTrue(rules.is_valid_pawn_move(6, 2, 4, 2, 'w'))

    def test_pawn_double_blocked_mid(self):
        data = _empty()
        data[6][2] = 'wP'
        data[5][2] = 'bP'
        rules = PieceRules(TextBoard(data))
        self.assertFalse(rules.is_valid_pawn_move(6, 2, 4, 2, 'w'))

    def test_pawn_capture_diagonal(self):
        data = _empty()
        data[4][4] = 'wP'
        data[3][5] = 'bN'
        rules = PieceRules(TextBoard(data))
        self.assertTrue(rules.is_valid_pawn_move(4, 4, 3, 5, 'w'))

    def test_pawn_cannot_capture_empty(self):
        data = _empty()
        data[4][4] = 'wP'
        rules = PieceRules(TextBoard(data))
        self.assertFalse(rules.is_valid_pawn_move(4, 4, 3, 5, 'w'))

    # ---- knight ----
    def test_knight_valid_l(self):
        data = _empty()
        rules = PieceRules(TextBoard(data))
        self.assertTrue(rules.is_valid_knight_move(4, 4, 6, 5))
        self.assertTrue(rules.is_valid_knight_move(4, 4, 2, 3))

    def test_knight_invalid(self):
        data = _empty()
        rules = PieceRules(TextBoard(data))
        self.assertFalse(rules.is_valid_knight_move(4, 4, 5, 5))

    # ---- rook ----
    def test_rook_clear_path(self):
        data = _empty()
        data[4][4] = 'wR'
        rules = PieceRules(TextBoard(data))
        self.assertTrue(rules.is_valid_sliding_move(4, 4, 4, 7, 'R'))

    def test_rook_blocked(self):
        data = _empty()
        data[4][4] = 'wR'
        data[4][6] = 'bN'
        rules = PieceRules(TextBoard(data))
        self.assertFalse(rules.is_valid_sliding_move(4, 4, 4, 7, 'R'))

    def test_rook_diagonal_invalid(self):
        data = _empty()
        rules = PieceRules(TextBoard(data))
        self.assertFalse(rules.is_valid_sliding_move(4, 4, 5, 5, 'R'))

    # ---- bishop ----
    def test_bishop_diagonal(self):
        data = _empty()
        data[4][4] = 'wB'
        rules = PieceRules(TextBoard(data))
        self.assertTrue(rules.is_valid_sliding_move(4, 4, 7, 7, 'B'))

    def test_bishop_straight_invalid(self):
        data = _empty()
        rules = PieceRules(TextBoard(data))
        self.assertFalse(rules.is_valid_sliding_move(4, 4, 4, 7, 'B'))

    # ---- king ----
    def test_king_one_step(self):
        data = _empty()
        rules = PieceRules(TextBoard(data))
        self.assertTrue(rules.is_valid_sliding_move(4, 4, 5, 5, 'K'))
        self.assertTrue(rules.is_valid_sliding_move(4, 4, 4, 5, 'K'))

    def test_king_two_steps_invalid(self):
        data = _empty()
        rules = PieceRules(TextBoard(data))
        self.assertFalse(rules.is_valid_sliding_move(4, 4, 4, 6, 'K'))


if __name__ == '__main__':
    unittest.main()
