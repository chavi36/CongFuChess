import unittest
from io import StringIO
from unittest.mock import patch

from application.kungfu_chess.model.board import TextBoard
from application.kungfu_chess.io.board_printer import print_board


class TestBoardPrinter(unittest.TestCase):
    def test_prints_all_rows(self):
        data = [['wK', '.'], ['bK', '.']]
        board = TextBoard(data)
        result = print_board(board)
        lines = result.strip().split('\n')
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], 'wK .')
        self.assertEqual(lines[1], 'bK .')


if __name__ == '__main__':
    unittest.main()
