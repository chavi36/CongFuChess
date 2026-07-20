"""
Integration tests for Kungfu Chess text scripts (.kfc).
Each test runs a full script through ScriptRunner and asserts the final
board state matches the expected output.
"""

import unittest
from application.kungfu_chess.model.board import TextBoard
from application.kungfu_chess.engine.game_engine import GameEngine
from application.kungfu_chess.input.controller import CommandExecutor
from application.kungfu_chess.texttests.script_parser import ScriptParser


def run_script(board_data, commands):
    """Helper: build engine + executor, run all commands, return board."""
    board = TextBoard(board_data)
    engine = GameEngine(board)
    executor = CommandExecutor(engine)
    for cmd_str in commands:
        cmd = ScriptParser.parse(cmd_str)
        if cmd:
            executor.execute(cmd)
    return board, engine


class Test01BoardParsing(unittest.TestCase):
    """01_board_parsing.kfc — print board returns the starting position."""

    def test_standard_start_position(self):
        data = [
            ['wR', 'wN', 'wB', 'wQ', 'wK', 'wB', 'wN', 'wR'],
            ['wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP'],
            ['.'] * 8, ['.'] * 8, ['.'] * 8, ['.'] * 8,
            ['bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP'],
            ['bR', 'bN', 'bB', 'bQ', 'bK', 'bB', 'bN', 'bR'],
        ]
        board, _ = run_script(data, ['print board'])
        self.assertEqual(board.get_piece(0, 0), 'wR')
        self.assertEqual(board.get_piece(7, 4), 'bK')
        self.assertEqual(board.get_piece(3, 3), '.')


class Test02ClickToMove(unittest.TestCase):
    """02_click_to_move.kfc — click-select then click-destination moves piece."""

    def test_rook_moves_right(self):
        data = [['.' for _ in range(8)] for _ in range(8)]
        data[4][4] = 'wR'
        board, _ = run_script(data, [
            'click 450 450',   # select wR at (4,4)  — ceil(450/100)-1 = 4
            'click 750 450',   # move to (4,7)       — ceil(750/100)-1 = 7
            'wait 4000',       # distance 3 → 3000 ms
        ])
        self.assertEqual(board.get_piece(4, 7), 'wR')
        self.assertEqual(board.get_piece(4, 4), '.')


class Test03RookMoves(unittest.TestCase):
    """03_rook_moves.kfc — rook moves vertically."""

    def test_rook_moves_up(self):
        data = [['.' for _ in range(8)] for _ in range(8)]
        data[2][3] = 'wR'
        board, _ = run_script(data, [
            'click 350 250',   # select wR at (2,3)
            'click 350 50',    # move to (0,3)
            'wait 3000',
        ])
        self.assertEqual(board.get_piece(0, 3), 'wR')
        self.assertEqual(board.get_piece(2, 3), '.')


class Test04InvalidMoves(unittest.TestCase):
    """04_invalid_moves.kfc — diagonal rook move is rejected."""

    def test_rook_diagonal_blocked(self):
        data = [['.' for _ in range(8)] for _ in range(8)]
        data[3][3] = 'wR'
        board, _ = run_script(data, [
            'click 350 350',   # select wR at (3,3)
            'click 450 250',   # diagonal → invalid
            'wait 2000',
        ])
        # piece should stay at origin
        self.assertEqual(board.get_piece(3, 3), 'wR')
        self.assertEqual(board.get_piece(2, 4), '.')


class Test05Capture(unittest.TestCase):
    """05_capture.kfc — rook captures enemy knight."""

    def test_rook_captures_enemy(self):
        data = [['.' for _ in range(8)] for _ in range(8)]
        data[3][3] = 'wR'
        data[3][5] = 'bN'
        board, _ = run_script(data, [
            'click 350 350',   # select wR at (3,3)
            'click 550 350',   # capture bN at (3,5) — distance 2 → 2000 ms
            'wait 3000',
        ])
        self.assertEqual(board.get_piece(3, 5), 'wR')
        self.assertEqual(board.get_piece(3, 3), '.')


class Test06GameOver(unittest.TestCase):
    """06_game_over.kfc — rook captures king ends the game."""

    def test_king_capture_ends_game(self):
        data = [['.' for _ in range(8)] for _ in range(8)]
        data[4][4] = 'wR'
        data[4][5] = 'bK'
        board, engine = run_script(data, [
            'click 450 450',   # select wR at (4,4)
            'click 550 450',   # capture bK at (4,5) — distance 1 → 1000 ms
            'wait 2000',
        ])
        self.assertTrue(engine.state.is_game_over())
        self.assertEqual(board.get_piece(4, 5), 'wR')

    def test_commands_ignored_after_game_over(self):
        data = [['.' for _ in range(8)] for _ in range(8)]
        data[4][4] = 'wR'
        data[4][5] = 'bK'
        data[0][0] = 'bR'
        board, engine = run_script(data, [
            'click 450 450',
            'click 550 450',
            'wait 2000',
            'click 50 50',     # try to move bR after game over
            'click 50 150',
            'wait 2000',
        ])
        self.assertTrue(engine.state.is_game_over())
        self.assertEqual(board.get_piece(0, 0), 'bR')  # bR did not move


class TestAirborneScenarios(unittest.TestCase):
    """Airborne jump + move interaction scenarios."""

    def test_jump_protects_piece(self):
        data = [['.' for _ in range(3)] for _ in range(3)]
        data[1][0] = 'wK'
        data[1][2] = 'bR'
        board, _ = run_script(data, [
            'jump 50 150',     # wK at (1,0) jumps — airborne 0..1000
            'click 250 150',   # select bR at (1,2)
            'click 50 150',    # bR starts moving at t=0, arrives at t=2000
            'wait 2500',
        ])
        # bR started at t=0 when wK was airborne → airborne capture: bR destroyed
        self.assertEqual(board.get_piece(1, 0), 'wK')
        self.assertEqual(board.get_piece(1, 2), '.')

    def test_airborne_piece_defeats_arriving_enemy(self):
        data = [['.' for _ in range(3)] for _ in range(3)]
        data[1][0] = 'wK'
        data[1][2] = 'bR'
        board, _ = run_script(data, [
            'jump 50 150',     # wK jumps at t=0, airborne 0..1000
            'click 250 150',   # select bR at t=0
            'click 50 150',    # bR starts moving at t=0, arrives at 2000
            'wait 1000',       # clock → 1000
            'print board',
        ])
        # bR arrives at 2000; wK was airborne at start_time=0 → bR destroyed
        self.assertEqual(board.get_piece(1, 0), 'wK')
        self.assertEqual(board.get_piece(1, 2), '.')


if __name__ == '__main__':
    unittest.main()
