import unittest
from io import StringIO
from unittest.mock import patch

from Core.io.board_parser import validate_board, load_from_input


class TestValidateBoard(unittest.TestCase):
    def test_valid_board(self):
        data = [['wK', '.', 'bK'], ['.', '.', '.']]
        validate_board(data)  # should not raise

    def test_empty_board(self):
        with self.assertRaises(ValueError):
            validate_board([])

    def test_row_width_mismatch(self):
        data = [['wK', 'bK'], ['.']]
        with self.assertRaises(ValueError):
            validate_board(data)

    def test_unknown_token(self):
        data = [['XX']]
        with self.assertRaises(ValueError):
            validate_board(data)

    def test_invalid_color(self):
        data = [['xK']]
        with self.assertRaises(ValueError):
            validate_board(data)


class TestLoadFromInput(unittest.TestCase):
    def test_load_valid(self):
        fake_input = "Board:\nwK . bK\nCommands:\nprint board\n"
        with patch('sys.stdin', StringIO(fake_input)):
            board, commands = load_from_input()
        self.assertEqual(board, [['wK', '.', 'bK']])
        self.assertEqual(commands, ['print board'])

    def test_load_no_header(self):
        with patch('sys.stdin', StringIO("garbage\n")):
            board, commands = load_from_input()
        self.assertIsNone(board)


if __name__ == '__main__':
    unittest.main()
