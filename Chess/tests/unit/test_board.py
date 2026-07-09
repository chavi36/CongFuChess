import unittest
from kungfu_chess.model.board import TextBoard
from kungfu_chess.model.config import EMPTY_SQUARE


def _std_board():
    return [
        ['wR', 'wN', 'wB', 'wQ', 'wK', 'wB', 'wN', 'wR'],
        ['wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP'],
        ['.'] * 8,
        ['.'] * 8,
        ['.'] * 8,
        ['.'] * 8,
        ['bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP'],
        ['bR', 'bN', 'bB', 'bQ', 'bK', 'bB', 'bN', 'bR'],
    ]


class TestTextBoard(unittest.TestCase):
    def setUp(self):
        self.board = TextBoard(_std_board())

    def test_get_piece(self):
        self.assertEqual(self.board.get_piece(0, 0), 'wR')
        self.assertEqual(self.board.get_piece(2, 0), EMPTY_SQUARE)

    def test_set_piece(self):
        self.board.set_piece(2, 2, 'wN')
        self.assertEqual(self.board.get_piece(2, 2), 'wN')

    def test_is_empty(self):
        self.assertTrue(self.board.is_empty(3, 3))
        self.assertFalse(self.board.is_empty(0, 0))

    def test_is_in_bounds(self):
        self.assertTrue(self.board.is_in_bounds(0, 0))
        self.assertFalse(self.board.is_in_bounds(8, 0))
        self.assertFalse(self.board.is_in_bounds(-1, 0))

    def test_out_of_bounds_returns_empty(self):
        self.assertEqual(self.board.get_piece(99, 99), EMPTY_SQUARE)

    def test_get_all_pieces_count(self):
        pieces = self.board.get_all_pieces()
        self.assertEqual(len(pieces), 32)
        self.assertEqual(len([p for p in pieces if p[2][0] == 'w']), 16)


if __name__ == '__main__':
    unittest.main()
