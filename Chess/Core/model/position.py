"""
Position model for Kungfu Chess.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    row: int
    col: int

    def offset(self, dr: int, dc: int) -> 'Position':
        return Position(self.row + dr, self.col + dc)

    def distance_to(self, other: 'Position') -> int:
        """Chebyshev distance (max of row/col deltas)."""
        return max(abs(self.row - other.row), abs(self.col - other.col))

    def __iter__(self):
        yield self.row
        yield self.col
