"""
Consolidated unit tests for Congfu Chess.
This single test module covers board, move validation, game engine, and command execution.
"""

import unittest
from io import StringIO
from unittest.mock import patch

from config import EMPTY_SQUARE
from game import TextBoard, GameEngine, MoveValidator
from main import CommandParser, CommandExecutor, Command


class TestBoard(unittest.TestCase):
    def setUp(self):
        self.board_data = [
            ['wR', 'wN', 'wB', 'wQ', 'wK', 'wB', 'wN', 'wR'],
            ['wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP'],
            ['bR', 'bN', 'bB', 'bQ', 'bK', 'bB', 'bN', 'bR'],
        ]
        self.board = TextBoard(self.board_data)

    def test_get_piece(self):
        self.assertEqual(self.board.get_piece(0, 0), 'wR')
        self.assertEqual(self.board.get_piece(1, 0), 'wP')
        self.assertEqual(self.board.get_piece(2, 0), '.')

    def test_set_piece(self):
        self.board.set_piece(2, 2, 'wN')
        self.assertEqual(self.board.get_piece(2, 2), 'wN')
        self.board.set_piece(2, 2, '.')
        self.assertEqual(self.board.get_piece(2, 2), '.')

    def test_is_empty(self):
        self.assertTrue(self.board.is_empty(2, 0))
        self.assertFalse(self.board.is_empty(0, 0))

    def test_get_all_pieces(self):
        pieces = self.board.get_all_pieces()
        white_pieces = [p for p in pieces if p[2][0] == 'w']
        black_pieces = [p for p in pieces if p[2][0] == 'b']
        self.assertEqual(len(white_pieces), 16)
        self.assertEqual(len(black_pieces), 16)
        self.assertEqual(len(pieces), 32)


class TestMoveValidator(unittest.TestCase):
    def test_knight_moves(self):
        board_data = [['.' for _ in range(8)] for _ in range(8)]
        board_data[4][4] = 'wN'
        board = TextBoard(board_data)
        validator = MoveValidator(board)
        self.assertTrue(validator.is_valid_move(4, 4, 6, 5))
        self.assertFalse(validator.is_valid_move(4, 4, 5, 4))

    def test_rook_blocked(self):
        board_data = [['.' for _ in range(8)] for _ in range(8)]
        board_data[4][4] = 'wR'
        board_data[4][6] = 'bN'
        board = TextBoard(board_data)
        validator = MoveValidator(board)
        self.assertTrue(validator.is_valid_move(4, 4, 4, 5))
        self.assertFalse(validator.is_valid_move(4, 4, 4, 7))

    def test_pawn_capture(self):
        board_data = [['.' for _ in range(8)] for _ in range(8)]
        board_data[4][0] = 'wP'
        board_data[3][1] = 'bN'
        board = TextBoard(board_data)
        validator = MoveValidator(board)
        self.assertTrue(validator.is_valid_move(4, 0, 3, 1))

    def test_pawn_capture_left(self):
        board_data = [['.' for _ in range(8)] for _ in range(8)]
        board_data[4][4] = 'wP'
        board_data[3][3] = 'bN'
        board = TextBoard(board_data)
        validator = MoveValidator(board)
        self.assertTrue(validator.is_valid_move(4, 4, 3, 3))


class TestGameEngine(unittest.TestCase):
    def setUp(self):
        board_data = [
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', 'wK', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', 'bN', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
        ]
        self.board = TextBoard(board_data)
        self.engine = GameEngine(self.board)

    def test_jump_schedule(self):
        self.assertTrue(self.engine.schedule_jump(5, 3, 0))
        self.assertTrue(self.engine.state.is_source_blocked(5, 3))

    def test_invalid_jump(self):
        self.assertFalse(self.engine.schedule_jump(0, 0, 0))
        self.assertFalse(self.engine.schedule_jump(10, 10, 0))

    def test_advance_time_unblocks(self):
        self.engine.schedule_jump(5, 3, 0)
        self.engine.advance_time(1500)
        self.assertFalse(self.engine.state.is_source_blocked(5, 3))

    def test_move_capture_ends_game(self):
        board_data = [
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', 'wR', 'bK', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
        ]
        board = TextBoard(board_data)
        engine = GameEngine(board)
        self.assertTrue(engine.schedule_move(4, 4, 4, 5, 0))
        engine.process_pending_moves(until_time=1000)
        self.assertTrue(engine.state.is_game_over())
        self.assertEqual(board.get_piece(4, 5), 'wR')

    def test_pawn_promotion(self):
        board_data = [
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['wP', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
        ]
        board = TextBoard(board_data)
        engine = GameEngine(board)
        self.assertTrue(engine.schedule_move(1, 0, 0, 0, 0))
        engine.process_pending_moves(until_time=1000)
        self.assertEqual(board.get_piece(0, 0), 'wQ')


class TestCommandParsingAndExecution(unittest.TestCase):
    def setUp(self):
        board_data = [
            ['wR', 'wN', 'wB', 'wQ', 'wK', 'wB', 'wN', 'wR'],
            ['wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP'],
            ['bR', 'bN', 'bB', 'bQ', 'bK', 'bB', 'bN', 'bR'],
        ]
        self.board = TextBoard(board_data)
        self.engine = GameEngine(self.board)
        self.executor = CommandExecutor(self.engine)

    def test_parse_print(self):
        cmd = CommandParser.parse("print board")
        self.assertEqual(cmd.cmd_type, 'print')

    def test_parse_click(self):
        cmd = CommandParser.parse("click 150 250")
        self.assertEqual(cmd.cmd_type, 'click')
        self.assertEqual(cmd.row, 2)
        self.assertEqual(cmd.col, 1)

    def test_execute_print(self):
        cmd = Command(cmd_type='print')
        with patch('sys.stdout', new=StringIO()) as fake_out:
            result = self.executor.execute(cmd)
            self.assertTrue(result)
            self.assertIn('wR', fake_out.getvalue())

    def test_click_select(self):
        cmd = Command(cmd_type='click', row=0, col=0)
        self.assertTrue(self.executor.execute(cmd))
        self.assertTrue(self.engine.state.has_selected_piece())

    def test_wait_advances_clock(self):
        cmd = Command(cmd_type='wait', time=500)
        self.assertTrue(self.executor.execute(cmd))
        self.assertEqual(self.engine.state.clock, 500)


class TestAirborneAndJumpScenarios(unittest.TestCase):
    def execute_commands(self, board_data, commands):
        board = TextBoard(board_data)
        engine = GameEngine(board)
        executor = CommandExecutor(engine)
        for cmd_str in commands:
            cmd = CommandParser.parse(cmd_str)
            self.assertIsNotNone(cmd)
            executor.execute(cmd)
        return board, engine

    def test_jump_lands_same_square(self):
        board_data = [
            ['.', '.', '.'],
            ['.', 'wK', '.'],
            ['.', '.', '.'],
        ]
        board, _ = self.execute_commands(board_data, [
            'jump 150 150',
            'wait 1000',
            'print board',
        ])
        self.assertEqual(board.board, [
            ['.', '.', '.'],
            ['.', 'wK', '.'],
            ['.', '.', '.'],
        ])

    def test_airborne_piece_captures_arriving_enemy(self):
        board_data = [
            ['.', '.', '.'],
            ['wK', '.', 'bR'],
            ['.', '.', '.'],
        ]
        board, _ = self.execute_commands(board_data, [
            'jump 50 150',
            'click 250 150',
            'click 50 150',
            'wait 1000',
            'print board',
        ])
        self.assertEqual(board.board, [
            ['.', '.', '.'],
            ['wK', '.', '.'],
            ['.', '.', '.'],
        ])

    def test_jump_too_late_does_not_save_piece(self):
        board_data = [
            ['.', '.', '.'],
            ['wK', '.', 'bR'],
            ['.', '.', '.'],
        ]
        board, _ = self.execute_commands(board_data, [
            'click 250 150',
            'click 50 150',
            'wait 1000',
            'jump 50 150',
            'print board',
        ])
        self.assertEqual(board.board, [
            ['.', '.', '.'],
            ['bR', '.', '.'],
            ['.', '.', '.'],
        ])

    def test_enemy_arrives_after_landing_captures_normally(self):
        board_data = [
            ['.', '.', '.', '.'],
            ['wK', '.', '.', 'bR'],
            ['.', '.', '.', '.'],
        ]
        board, _ = self.execute_commands(board_data, [
            'jump 50 150',
            'wait 1000',
            'click 350 150',
            'click 50 150',
            'wait 3000',
            'print board',
        ])
        self.assertEqual(board.board, [
            ['.', '.', '.', '.'],
            ['bR', '.', '.', '.'],
            ['.', '.', '.', '.'],
        ])

    def test_cannot_jump_while_moving(self):
        board_data = [
            ['wR', '.', '.'],
            ['.', '.', '.'],
            ['.', '.', '.'],
        ]
        board, _ = self.execute_commands(board_data, [
            'click 50 50',
            'click 250 50',
            'wait 500',
            'jump 50 50',
            'wait 1500',
            'print board',
        ])
        self.assertEqual(board.board, [
            ['.', '.', 'wR'],
            ['.', '.', '.'],
            ['.', '.', '.'],
        ])

    def test_airborne_capture_only_enemy(self):
        board_data = [
            ['.', '.', '.'],
            ['wK', '.', 'wR'],
            ['.', '.', '.'],
        ]
        board, _ = self.execute_commands(board_data, [
            'jump 50 150',
            'click 250 150',
            'click 50 150',
            'wait 1000',
            'print board',
        ])
        self.assertEqual(board.board, [
            ['.', '.', '.'],
            ['wK', '.', 'wR'],
            ['.', '.', '.'],
        ])


if __name__ == '__main__':
    unittest.main()
