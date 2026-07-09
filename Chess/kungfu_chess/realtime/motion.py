"""
Active motion tracking for Kungfu Chess.

MoveMotion  — a piece that is currently travelling from one square to another.
JumpMotion  — a piece that is airborne (jumped in place, not moving).

Both are removed from the active set once they land.
"""

from dataclasses import dataclass


@dataclass
class MoveMotion:
    """A piece en route from (from_row, from_col) to (to_row, to_col)."""
    from_row:   int
    from_col:   int
    to_row:     int
    to_col:     int
    start_time: int
    arrival_time: int
    piece_code: str       # snapshot at scheduling time


@dataclass
class AirborneEvent:
    """A piece that jumped in place — it is immune to capture while airborne."""
    row:        int
    col:        int
    start_time: int
    end_time:   int
    color:      str
