"""
Game engine for Kungfu Chess — coordinator only.

Responsibilities
----------------
- Accept move/jump requests from the controller.
- Check preconditions: bounds, source not blocked, source not empty.
- Ask RuleEngine whether the move is geometrically legal.
- Ask RealTimeArbiter whether an airborne conflict cancels the move.
- Hand the approved motion to RealTimeArbiter for tracking.
- Drive time forward on advance_time() by delegating to the arbiter.

Does NOT touch the board directly.
Does NOT decide whether a king was captured.
Does NOT decide when pieces arrive.
"""

from typing import Optional

from kungfu_chess.model.board import BoardInterface
from kungfu_chess.model.game_state import GameState
from kungfu_chess.realtime.motion import MoveMotion, AirborneEvent
from kungfu_chess.realtime.real_time_arbiter import RealTimeArbiter
from kungfu_chess.rules.rule_engine import RuleEngine
from kungfu_chess.model.config import TIME_CONFIG, EMPTY_SQUARE


class GameEngine:

    def __init__(self, board: BoardInterface):
        self.board       = board
        self.state       = GameState(board)
        self.rule_engine = RuleEngine(board)
        self.arbiter     = RealTimeArbiter(board, self.state)
        self._validate_board()

    # ------------------------------------------------------------------
    # Board validation (startup check only)
    # ------------------------------------------------------------------

    def _validate_board(self) -> None:
        if not self.board.get_width() or not self.board.get_height():
            raise ValueError("Board must have non-zero dimensions")
        for row, col, piece_code in self.board.get_all_pieces():
            if len(piece_code) != 2:
                raise ValueError(f"Invalid piece code at ({row}, {col}): {piece_code}")
            color, piece_type = piece_code[0], piece_code[1]
            if color not in ['w', 'b']:
                raise ValueError(f"Invalid piece color: {color}")
            if piece_type not in ['K', 'Q', 'R', 'B', 'N', 'P']:
                raise ValueError(f"Invalid piece type: {piece_type}")

    # ------------------------------------------------------------------
    # Time advancement — delegates entirely to the arbiter
    # ------------------------------------------------------------------

    def advance_time(self, wait_time: int) -> None:
        """Advance the clock by wait_time ms and resolve all arrivals."""
        target_time = self.state.clock + wait_time
        self.arbiter.advance_to(target_time)
        self.state.clock = target_time

    # process_pending_moves kept for backward-compat with controller/tests
    def process_pending_moves(self, until_time: Optional[int] = None) -> None:
        target = until_time if until_time is not None else self.state.clock
        self.arbiter.advance_to(target)

    # ------------------------------------------------------------------
    # Public API — schedule requests
    # ------------------------------------------------------------------

    def schedule_move(self, from_row: int, from_col: int,
                      to_row: int, to_col: int, start_time: int) -> bool:
        """
        Validate preconditions and hand the motion to the arbiter.
        Returns False if the move cannot be scheduled.
        """
        # 1. Bounds.
        if not self.board.is_in_bounds(from_row, from_col):
            return False
        if not self.board.is_in_bounds(to_row, to_col):
            return False
        # 2. Source state.
        if self.state.is_source_blocked(from_row, from_col):
            return False
        if self.board.is_empty(from_row, from_col):
            return False
        # 3. Rule check.
        if not self.rule_engine.is_valid_move(from_row, from_col, to_row, to_col):
            return False

        distance     = self.rule_engine.get_move_distance(from_row, from_col, to_row, to_col)
        arrival_time = start_time + distance * TIME_CONFIG['move_time_per_square']
        piece_color  = self.board.get_piece(from_row, from_col)[0]
        piece_code   = self.board.get_piece(from_row, from_col)

        # 4. Airborne conflict at scheduling time.
        if self.arbiter.has_airborne_conflict(
                to_row, to_col, piece_color, start_time, start_time):
            self.board.set_piece(from_row, from_col, EMPTY_SQUARE)  # piece destroyed
            return False

        # 5. Hand off to arbiter.
        motion = MoveMotion(
            from_row=from_row, from_col=from_col,
            to_row=to_row,     to_col=to_col,
            start_time=start_time, arrival_time=arrival_time,
            piece_code=piece_code,
        )
        self.arbiter.register_move(motion)
        self.state.block_source(from_row, from_col)
        return True

    def schedule_jump(self, row: int, col: int, start_time: int) -> bool:
        """Register a jump (airborne) event for the piece at (row, col)."""
        if not self.board.is_in_bounds(row, col):
            return False
        if self.board.is_empty(row, col):
            return False
        if self.state.is_source_blocked(row, col):
            return False

        piece_color = self.board.get_piece(row, col)[0]
        end_time    = start_time + TIME_CONFIG['jump_duration']
        jump        = AirborneEvent(row=row, col=col,
                                    start_time=start_time, end_time=end_time,
                                    color=piece_color)
        self.arbiter.register_jump(jump)
        self.state.block_source(row, col)
        return True
