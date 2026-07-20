import unittest
from application.kungfu_chess.model.board import TextBoard
from application.kungfu_chess.model.game_state import GameState
from application.kungfu_chess.realtime.motion import AirborneEvent, MoveMotion
from application.kungfu_chess.realtime.real_time_arbiter import RealTimeArbiter


def _empty(rows=4, cols=4):
    return [['.' for _ in range(cols)] for _ in range(rows)]


def _make_arbiter():
    board = TextBoard(_empty())
    state = GameState(board)
    arbiter = RealTimeArbiter(board, state)
    return arbiter, board, state


class TestAirborneConflict(unittest.TestCase):
    def test_no_airborne_no_conflict(self):
        arbiter, _, _ = _make_arbiter()
        self.assertFalse(arbiter.has_airborne_conflict(1, 1, 'w', 0, 500))

    def test_enemy_airborne_instant_conflict(self):
        arbiter, _, state = _make_arbiter()
        jump = AirborneEvent(1, 1, start_time=0, end_time=1000, color='b')
        arbiter.register_jump(jump)
        self.assertTrue(arbiter.has_airborne_conflict(1, 1, 'w', 0, 500))

    def test_friendly_airborne_no_conflict(self):
        arbiter, _, state = _make_arbiter()
        jump = AirborneEvent(1, 1, start_time=0, end_time=1000, color='w')
        arbiter.register_jump(jump)
        self.assertFalse(arbiter.has_airborne_conflict(1, 1, 'w', 0, 500))

    def test_enemy_airborne_after_arrival_no_conflict(self):
        arbiter, _, state = _make_arbiter()
        jump = AirborneEvent(1, 1, start_time=2000, end_time=3000, color='b')
        arbiter.register_jump(jump)
        self.assertFalse(arbiter.has_airborne_conflict(1, 1, 'w', 0, 500))


class TestArrivalResolution(unittest.TestCase):
    def test_piece_moves_to_empty_square(self):
        board = TextBoard(_empty())
        board.set_piece(0, 0, 'wR')
        state = GameState(board)
        arbiter = RealTimeArbiter(board, state)
        motion = MoveMotion(0, 0, 0, 2, start_time=0,
                            arrival_time=2000, piece_code='wR')
        arbiter.register_move(motion)
        state.block_source(0, 0)
        arbiter.advance_to(2000)
        self.assertEqual(board.get_piece(0, 2), 'wR')
        self.assertEqual(board.get_piece(0, 0), '.')
        self.assertFalse(state.is_source_blocked(0, 0))

    def test_piece_captures_enemy(self):
        board = TextBoard(_empty())
        board.set_piece(0, 0, 'wR')
        board.set_piece(0, 2, 'bN')
        state = GameState(board)
        arbiter = RealTimeArbiter(board, state)
        motion = MoveMotion(0, 0, 0, 2, start_time=0,
                            arrival_time=2000, piece_code='wR')
        arbiter.register_move(motion)
        state.block_source(0, 0)
        arbiter.advance_to(2000)
        self.assertEqual(board.get_piece(0, 2), 'wR')
        self.assertEqual(board.get_piece(0, 0), '.')

    def test_king_capture_ends_game(self):
        board = TextBoard(_empty())
        board.set_piece(0, 0, 'wR')
        board.set_piece(0, 1, 'bK')
        state = GameState(board)
        arbiter = RealTimeArbiter(board, state)
        motion = MoveMotion(0, 0, 0, 1, start_time=0,
                            arrival_time=1000, piece_code='wR')
        arbiter.register_move(motion)
        state.block_source(0, 0)
        arbiter.advance_to(1000)
        self.assertTrue(state.is_game_over())
        self.assertEqual(board.get_piece(0, 1), 'wR')

    def test_no_board_change_after_game_over(self):
        board = TextBoard(_empty())
        board.set_piece(0, 0, 'wR')
        board.set_piece(0, 1, 'bK')
        board.set_piece(1, 0, 'wB')
        state = GameState(board)
        arbiter = RealTimeArbiter(board, state)
        # First move captures the king at t=1000
        m1 = MoveMotion(0, 0, 0, 1, 0, 1000, 'wR')
        arbiter.register_move(m1)
        state.block_source(0, 0)
        # Second move arrives after game over at t=2000
        m2 = MoveMotion(1, 0, 1, 2, 0, 2000, 'wB')
        arbiter.register_move(m2)
        state.block_source(1, 0)
        arbiter.advance_to(3000)
        # wR captured the king → game over
        self.assertTrue(state.is_game_over())
        # wB should NOT have moved
        self.assertEqual(board.get_piece(1, 0), 'wB')
        self.assertEqual(board.get_piece(1, 2), '.')

    def test_jump_unblocks_after_landing(self):
        board = TextBoard(_empty())
        board.set_piece(2, 2, 'wK')
        state = GameState(board)
        arbiter = RealTimeArbiter(board, state)
        jump = AirborneEvent(2, 2, start_time=0, end_time=1000, color='w')
        arbiter.register_jump(jump)
        state.block_source(2, 2)
        arbiter.advance_to(1000)
        self.assertFalse(state.is_source_blocked(2, 2))
        self.assertEqual(board.get_piece(2, 2), 'wK')

    def test_pawn_promotion_on_arrival(self):
        board = TextBoard(_empty())
        board.set_piece(1, 0, 'wP')
        state = GameState(board)
        arbiter = RealTimeArbiter(board, state)
        motion = MoveMotion(1, 0, 0, 0, start_time=0,
                            arrival_time=1000, piece_code='wP')
        arbiter.register_move(motion)
        state.block_source(1, 0)
        arbiter.advance_to(1000)
        self.assertEqual(board.get_piece(0, 0), 'wQ')

    def test_pawn_capture_king_does_not_promote(self):
        board = TextBoard(_empty())
        board.set_piece(1, 0, 'wP')
        board.set_piece(0, 0, 'bK')
        state = GameState(board)
        arbiter = RealTimeArbiter(board, state)
        motion = MoveMotion(1, 0, 0, 0, start_time=0,
                            arrival_time=1000, piece_code='wP')
        arbiter.register_move(motion)
        state.block_source(1, 0)
        arbiter.advance_to(1000)
        self.assertTrue(state.is_game_over())
        self.assertEqual(board.get_piece(0, 0), 'wP')


if __name__ == '__main__':
    unittest.main()
