import unittest
from application.kungfu_chess.model.board import TextBoard
from application.kungfu_chess.engine.game_engine import GameEngine


def _empty(rows=8, cols=8):
    return [['.' for _ in range(cols)] for _ in range(rows)]


class TestGameEngine(unittest.TestCase):
    def test_schedule_jump_blocks_source(self):
        data = _empty()
        data[3][3] = 'wK'
        engine = GameEngine(TextBoard(data))
        self.assertTrue(engine.schedule_jump(3, 3, 0))
        self.assertTrue(engine.state.is_source_blocked(3, 3))

    def test_jump_unblocks_after_advance(self):
        data = _empty()
        data[3][3] = 'wK'
        engine = GameEngine(TextBoard(data))
        engine.schedule_jump(3, 3, 0)
        engine.advance_time(1500)
        self.assertFalse(engine.state.is_source_blocked(3, 3))

    def test_invalid_jump_empty_square(self):
        engine = GameEngine(TextBoard(_empty()))
        self.assertFalse(engine.schedule_jump(0, 0, 0))

    def test_invalid_jump_out_of_bounds(self):
        engine = GameEngine(TextBoard(_empty()))
        self.assertFalse(engine.schedule_jump(99, 99, 0))

    def test_move_captures_king_ends_game(self):
        data = _empty()
        data[4][4] = 'wR'
        data[4][5] = 'bK'
        engine = GameEngine(TextBoard(data))
        self.assertTrue(engine.schedule_move(4, 4, 4, 5, 0))
        engine.process_pending_moves(until_time=1000)
        self.assertTrue(engine.state.is_game_over())

    def test_pawn_promotion(self):
        data = _empty()
        data[1][0] = 'wP'
        engine = GameEngine(TextBoard(data))
        self.assertTrue(engine.schedule_move(1, 0, 0, 0, 0))
        engine.process_pending_moves(until_time=1000)
        self.assertEqual(engine.board.get_piece(0, 0), 'wQ')

    def test_cannot_move_blocked_piece(self):
        data = _empty()
        data[4][4] = 'wR'
        engine = GameEngine(TextBoard(data))
        engine.state.block_source(4, 4)
        self.assertFalse(engine.schedule_move(4, 4, 4, 5, 0))

    def test_advance_time_processes_events(self):
        data = _empty()
        data[4][4] = 'wR'
        engine = GameEngine(TextBoard(data))
        engine.schedule_move(4, 4, 4, 6, 0)   # distance 2 → arrives at t=2000
        engine.advance_time(3000)
        self.assertEqual(engine.board.get_piece(4, 6), 'wR')
        self.assertEqual(engine.board.get_piece(4, 4), '.')


if __name__ == '__main__':
    unittest.main()
