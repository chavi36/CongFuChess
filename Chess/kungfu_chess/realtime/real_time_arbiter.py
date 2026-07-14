"""
Real-time arbiter for Kungfu Chess.

Owns all active motions (moves and jumps).
Advances simulated time and resolves arrivals atomically.

Collision handling is delegated to CollisionRules:
- En-route: both pieces stop at their last legal position.
- Destination same color: later piece is cancelled.
- Destination enemy color: later piece captures.
"""

from typing import List, Optional

from kungfu_chess.model.board import BoardInterface
from kungfu_chess.model.game_state import GameState
from kungfu_chess.realtime.motion import MoveMotion, AirborneEvent
from kungfu_chess.rules.collision_rules import CollisionRules
from kungfu_chess.model.config import EMPTY_SQUARE, TIME_CONFIG, get_pawn_config, PieceType, COOLDOWN_CONFIG


class RealTimeArbiter:

    def __init__(self, board: BoardInterface, state: GameState, rule_engine=None):
        self._board  = board
        self._state  = state
        self._active_moves: List[MoveMotion]    = []
        self._active_jumps: List[AirborneEvent] = []
        self._collision = CollisionRules(board, rule_engine)

    def set_rule_engine(self, rule_engine) -> None:
        self._collision = CollisionRules(self._board, rule_engine)

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def register_move(self, motion: MoveMotion) -> None:
        self._active_moves.append(motion)

    def register_jump(self, jump: AirborneEvent) -> None:
        self._active_jumps.append(jump)
        self._state.add_airborne(jump)

    # ------------------------------------------------------------------
    # Airborne-conflict query
    # ------------------------------------------------------------------

    def has_airborne_conflict(self, row: int, col: int,
                               moving_color: str,
                               start_time: int,
                               arrival_time: int) -> bool:
        for jump in self._state.get_airborne_at_square(row, col):
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
        self._resolve_en_route_collisions()

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
                if event in self._active_moves:
                    self._active_moves.remove(event)
            else:
                self._state.unblock_source(event.row, event.col)
                self._active_jumps.remove(event)
                # cooldown after landing from jump
                piece_code = self._board.get_piece(event.row, event.col)
                if piece_code != EMPTY_SQUARE:
                    piece_type = piece_code[1]
                    cooldown = COOLDOWN_CONFIG.get(piece_type, {}).get('jump', 0)
                    if cooldown:
                        self._state.set_cooldown(event.row, event.col, t + cooldown)

    # ------------------------------------------------------------------
    # En-route collision resolution
    # ------------------------------------------------------------------

    def _resolve_en_route_collisions(self) -> None:
        """
        Detect pairs of active moves that share a path square and stop
        both at their last legal position before the collision square.
        """
        moves = list(self._active_moves)
        cancelled = set()

        for i, a in enumerate(moves):
            for j, b in enumerate(moves):
                if j <= i:
                    continue
                if id(a) in cancelled or id(b) in cancelled:
                    continue
                if not self._collision.is_en_route_collision(a, b):
                    continue

                # Find the shared square(s) — use the first one in a's path
                shared = set(a.path[:-1]) & set(b.path[:-1])
                if not shared:
                    continue
                # Pick the earliest shared square along a's path
                collision_square = next(
                    sq for sq in a.path[:-1] if sq in shared)

                self._stop_at_last_legal(a, collision_square)
                self._stop_at_last_legal(b, collision_square)
                cancelled.add(id(a))
                cancelled.add(id(b))

    def _stop_at_last_legal(self, motion: MoveMotion,
                             collision_square) -> None:
        """
        Move the piece to its last legal position before collision_square,
        then remove the motion from active moves.
        """
        self._active_moves.remove(motion)
        self._state.unblock_source(motion.from_row, motion.from_col)

        if self._state.is_game_over():
            return

        last_legal = self._collision.last_legal_position(motion, collision_square)
        if last_legal is None:
            # Jumping piece or no legal square — stays at source (already there)
            return

        piece_code = self._board.get_piece(motion.from_row, motion.from_col)
        if piece_code == EMPTY_SQUARE:
            return

        self._board.set_piece(motion.from_row, motion.from_col, EMPTY_SQUARE)
        self._board.set_piece(last_legal[0], last_legal[1], piece_code)

    # ------------------------------------------------------------------
    # Destination arrival resolution
    # ------------------------------------------------------------------

    def _resolve_arrival(self, motion: MoveMotion) -> None:
        from_row, from_col = motion.from_row, motion.from_col
        to_row,   to_col   = motion.to_row,   motion.to_col

        self._state.unblock_source(from_row, from_col)

        if self._state.is_game_over():
            return

        if self._board.is_empty(from_row, from_col):
            return

        piece_code  = self._board.get_piece(from_row, from_col)
        piece_color = piece_code[0]
        piece_type  = piece_code[1]
        target      = self._board.get_piece(to_row, to_col)

        # Check for destination collision with another active motion
        rival = self._find_destination_rival(motion)
        if rival is not None:
            winner, _ = self._collision.resolve_destination_collision(motion, rival)
            if winner is not motion:
                # This motion loses — don't move
                return

        # Same-color piece already on destination (arrived earlier)
        if target != EMPTY_SQUARE and target[0] == piece_color:
            return

        # Pawn promotion
        if piece_type == 'P':
            config = get_pawn_config(self._board.get_height())[
                'white' if piece_color == 'w' else 'black']
            if to_row == config['promotion_row']:
                piece_code = piece_color + PieceType.QUEEN.value

        self._board.set_piece(from_row, from_col, EMPTY_SQUARE)
        self._board.set_piece(to_row, to_col, piece_code)

        # cooldown after arrival
        piece_type = piece_code[1]
        cooldown = COOLDOWN_CONFIG.get(piece_type, {}).get('move', 0)
        if cooldown:
            self._state.set_cooldown(to_row, to_col, motion.arrival_time + cooldown)

        if len(target) > 1 and target[1] == 'K':
            self._state.end_game()

    def _find_destination_rival(self, motion: MoveMotion) -> Optional[MoveMotion]:
        """Return another active motion heading to the same destination, if any."""
        for other in self._active_moves:
            if other is not motion and other.to_row == motion.to_row and other.to_col == motion.to_col:
                return other
        return None
