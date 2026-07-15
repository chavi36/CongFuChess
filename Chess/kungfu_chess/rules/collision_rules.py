"""
Collision rules for Kungfu Chess.

Two types of collisions:
- En-route: two pieces try to pass through the same square at the same time.
  Both stop at their last legal position before the collision square.
  For sliding pieces (Q, R, B, P) — the last square before the collision.
  For jumping pieces (N, K) — no intermediate squares, so they don't move at all.

- Destination: two pieces target the same square.
  Same color  — the later one (higher start_time) simply doesn't move.
  Enemy color — the later one captures (replaces the earlier arrival).
"""

from typing import Optional, Tuple, List
from kungfu_chess.realtime.motion import MoveMotion
from kungfu_chess.model.board import BoardInterface


class CollisionRules:

    def __init__(self, board: BoardInterface, rule_engine):
        self._board = board
        self._rule_engine = rule_engine

    # ------------------------------------------------------------------
    # En-route collision
    # ------------------------------------------------------------------

    def is_en_route_collision(self, a: MoveMotion, b: MoveMotion) -> bool:
        """True if the two motions occupy the same square at the same time."""
        if not a.path or not b.path:
            return False
        shared = set(a.path[:-1]) & set(b.path[:-1])
        if not shared:
            return False
        for square in shared:
            if self._time_at_square(a, square) == self._time_at_square(b, square):
                return True
        return False

    @staticmethod
    def _time_at_square(motion: MoveMotion, square: tuple) -> int:
        """Return the clock time when motion passes through square."""
        idx = motion.path.index(square)
        seg_count = len(motion.path) - 1
        duration  = motion.arrival_time - motion.start_time
        return motion.start_time + (duration * idx // seg_count) if seg_count else motion.start_time

    def last_legal_position(self, motion: MoveMotion,
                            blocked_square: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        """
        Return the last legal square the piece can reach before blocked_square.
        Iterates the path in reverse (excluding destination) and returns the
        first square for which is_valid_move from source is legal.
        If none found, returns None (piece stays at source).
        """
        if not motion.path or len(motion.path) < 2:
            return None
        # path includes source and destination; intermediate squares are path[1:-1]
        intermediate = motion.path[1:-1]
        for square in reversed(intermediate):
            if square == blocked_square:
                continue
            row, col = square
            if self._rule_engine.is_valid_move(
                    motion.from_row, motion.from_col, row, col):
                return square
        return None

    # ------------------------------------------------------------------
    # Destination collision
    # ------------------------------------------------------------------

    def resolve_destination_collision(self, a: MoveMotion,
                                      b: MoveMotion) -> Tuple[Optional[MoveMotion],
                                                               Optional[MoveMotion]]:
        """
        Given two motions heading to the same square, return (winner, loser).
        winner proceeds normally, loser is cancelled (returns None for its slot).

        Same color  — earlier (lower start_time) proceeds, later is cancelled.
        Enemy color — later (higher start_time) proceeds (captures), earlier cancelled.
        """
        a_color = a.piece_code[0]
        b_color = b.piece_code[0]
        later, earlier = (a, b) if a.start_time >= b.start_time else (b, a)

        if a_color == b_color:
            return earlier, None   # later one doesn't move
        else:
            return later, None     # later one captures
