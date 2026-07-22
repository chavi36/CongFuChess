import unittest
from io import StringIO
from unittest.mock import patch

from Core.model.board import TextBoard
from Core.engine.game_engine import GameEngine
from Core.input.controller import Command, CommandExecutor


def _std_engine():
    data = [
        ['wR', 'wN', 'wB', 'wQ', 'wK', 'wB', 'wN', 'wR'],
        ['wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP'],
        ['.'] * 8, ['.'] * 8, ['.'] * 8, ['.'] * 8,
        ['bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP'],
        ['bR', 'bN', 'bB', 'bQ', 'bK', 'bB', 'bN', 'bR'],
    ]
    return GameEngine(TextBoard(data))


class TestCommandExecutor(unittest.TestCase):
    def setUp(self):
        self.engine = _std_engine()
        self.executor = CommandExecutor(self.engine)

    def test_click_selects_piece(self):
        self.assertTrue(self.executor.execute(Command(cmd_type='click', row=0, col=0)))
        self.assertTrue(self.engine.state.has_selected_piece())

    def test_click_deselects_same_piece(self):
        self.executor.execute(Command(cmd_type='click', row=0, col=0))
        self.executor.execute(Command(cmd_type='click', row=0, col=0))
        self.assertFalse(self.engine.state.has_selected_piece())

    def test_wait_advances_clock(self):
        self.executor.execute(Command(cmd_type='wait', time=750))
        self.assertEqual(self.engine.state.clock, 750)

    def test_print_outputs_board(self):
        from Core.io.board_printer import print_board
        with patch('sys.stdout', new=StringIO()) as out:
            executor = CommandExecutor(self.engine, on_print=lambda b: print(print_board(b), flush=True))
            executor.execute(Command(cmd_type='print'))
            self.assertIn('wR', out.getvalue())

    def test_no_action_after_game_over(self):
        self.engine.state.end_game()
        result = self.executor.execute(Command(cmd_type='click', row=0, col=0))
        self.assertFalse(result)

    def test_click_out_of_bounds_clears_selection(self):
        # Select a piece first
        self.executor.execute(Command(cmd_type='click', row=0, col=0))
        self.assertTrue(self.engine.state.has_selected_piece())
        # Click way outside the board
        self.executor.execute(Command(cmd_type='click', row=99, col=99))
        self.assertFalse(self.engine.state.has_selected_piece())

    def test_click_out_of_bounds_without_selection_returns_false(self):
        result = self.executor.execute(Command(cmd_type='click', row=-1, col=0))
        self.assertFalse(result)
        self.assertFalse(self.engine.state.has_selected_piece())

    def test_invalid_move_does_not_move_piece(self):
        # Rook cannot move diagonally — engine rejects it
        data = [['.' for _ in range(4)] for _ in range(4)]
        data[0][0] = 'wR'
        engine = GameEngine(TextBoard(data))
        executor = CommandExecutor(engine)
        executor.execute(Command(cmd_type='click', row=0, col=0))   # select wR
        executor.execute(Command(cmd_type='click', row=1, col=1))   # diagonal → invalid
        engine.advance_time(2000)
        # piece must stay where it was
        self.assertEqual(engine.board.get_piece(0, 0), 'wR')
        self.assertEqual(engine.board.get_piece(1, 1), '.')

    def test_controller_does_not_check_move_validity_itself(self):
        # The controller must delegate validity to schedule_move, not duplicate the check.
        # We verify that clicking an invalid destination still clears the selection
        # (controller did its job) but the piece does not move (engine rejected it).
        data = [['.' for _ in range(4)] for _ in range(4)]
        data[0][0] = 'wR'
        engine = GameEngine(TextBoard(data))
        executor = CommandExecutor(engine)
        executor.execute(Command(cmd_type='click', row=0, col=0))
        self.assertTrue(engine.state.has_selected_piece())
        executor.execute(Command(cmd_type='click', row=1, col=1))   # invalid for rook
        # selection cleared regardless
        self.assertFalse(engine.state.has_selected_piece())
        # but piece did not move
        self.assertEqual(engine.board.get_piece(0, 0), 'wR')


if __name__ == '__main__':
    unittest.main()
