"""
Real-time arbiter for Kungfu Chess.

Owns all active motions (moves and jumps).
Advances simulated time and resolves arrivals atomically:

  1. Remove the piece from its source square.
  2. If an enemy occupies the destination — it is captured.
  3. Place the piece on the destination square.
  4. If the captured piece was a king — report game-over to GameState.

The board is never mutated between scheduling and arrival.
After game-over the board is frozen (no further arrivals are applied).
"""

from typing import List, Callable, Optional

from kungfu_chess.model.board import BoardInterface
from kungfu_chess.model.game_state import GameState
from kungfu_chess.realtime.motion import MoveMotion, AirborneEvent
from kungfu_chess.model.config import EMPTY_SQUARE, TIME_CONFIG, PAWN_CONFIG, PieceType


class RealTimeArbiter:
    """
    Manages active motions and resolves their outcomes.

    Responsibilities
    ----------------
    - Track every active MoveMotion and AirborneEvent.
    - Provide the airborne-conflict query used at scheduling time.
    - Apply arrivals atomically when advance_to() is called.
    - Detect king capture and call state.end_game().
    - Respect game-over: no board changes after the game ends.
    """

    def __init__(self, board: BoardInterface, state: GameState):
        self._board  = board
        self._state  = state
        self._active_moves:   List[MoveMotion]   = []
        self._active_jumps:   List[AirborneEvent] = []

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def register_move(self, motion: MoveMotion) -> None:
        """Add a newly scheduled move to the active set."""
        self._active_moves.append(motion)

    def register_jump(self, jump: AirborneEvent) -> None:
        """Add a newly scheduled jump to the active set."""
        self._active_jumps.append(jump)
        self._state.add_airborne(jump)   # keep history for conflict checks

    # ------------------------------------------------------------------
    # Airborne-conflict query (called at scheduling time by GameEngine)
    # ------------------------------------------------------------------

    def has_airborne_conflict(self, row: int, col: int,
                               moving_color: str,
                               start_time: int,
                               arrival_time: int) -> bool:
        """
        Return True if an enemy piece was airborne over (row, col)
        during [start_time, arrival_time], meaning the moving piece
        would be destroyed.
        """
        for jump in self._active_jumps:
            if jump.row != row or jump.col != col:
                continue
            if jump.color == moving_color:
                continue
            if TIME_CONFIG['check_airborne_capture_instant']:
                if jump.start_time <= start_time < jump.end_time:
                    return True
            if TIME_CONFIG['check_airborne_capture_arrival']:
                if jump.start_time <= arrival_time < jump.end_time:
                    return True
        return False

    # ------------------------------------------------------------------
    # Time advancement
    # ------------------------------------------------------------------

    def advance_to(self, target_time: int) -> None:
        """
        Process all arrivals whose arrival_time <= target_time, in order.
        Each arrival is resolved atomically.
        """
        # Collect all landing events sorted by time.
        pending = []
        for motion in list(self._active_moves):
            if motion.arrival_time <= target_time:
                pending.append(('move', motion.arrival_time, motion))
        for jump in list(self._active_jumps):
            if jump.end_time <= target_time:
                pending.append(('jump', jump.end_time, jump))

        pending.sort(key=lambda x: x[1])

        for kind, t, event in pending:
            if kind == 'move':
                self._resolve_arrival(event)
                self._active_moves.remove(event)
            else:
                self._state.unblock_source(event.row, event.col)
                self._active_jumps.remove(event)

    # ------------------------------------------------------------------
    # Atomic arrival resolution
    # ------------------------------------------------------------------

    def _resolve_arrival(self, motion: MoveMotion) -> None:
        """
        Apply a MoveMotion atomically.
        If the game is already over, skip all board mutations.
        """
        from_row, from_col = motion.from_row, motion.from_col
        to_row,   to_col   = motion.to_row,   motion.to_col

        # Always unblock the source (even if game is over).
        self._state.unblock_source(from_row, from_col)

        if self._state.is_game_over():
            return

        # The piece may have been wiped by an airborne capture earlier.
        if self._board.is_empty(from_row, from_col):
            return

        piece_code  = self._board.get_piece(from_row, from_col)
        piece_color = piece_code[0]
        piece_type  = piece_code[1]

        # Friendly-fire guard: another friendly piece may have arrived first.
        target = self._board.get_piece(to_row, to_col)
        if target != EMPTY_SQUARE and target[0] == piece_color:
            return

        # Pawn promotion.
        if piece_type == 'P':
            config = PAWN_CONFIG['white' if piece_color == 'w' else 'black']
            if to_row == config['promotion_row']:
                piece_code = piece_color + PieceType.QUEEN.value

        # --- Atomic board update ---
        # 1. Remove from source.
        self._board.set_piece(from_row, from_col, EMPTY_SQUARE)
        # 2. Capture enemy on destination (target already read above).
        # 3. Place piece on destination.
        self._board.set_piece(to_row, to_col, piece_code)

        # 4. If captured piece was a king — end the game.
        if len(target) > 1 and target[1] == 'K':
            self._state.end_game()
