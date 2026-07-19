from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Tuple


def cell_to_notation(row: int, col: int) -> str:
    """Convert (row, col) to chess notation e.g. (6, 0) -> a2"""
    return chr(ord('a') + col) + str(8 - row)


@dataclass
class MoveObserver:
    """Records every arrived move for one color as (wall_time, piece_type, from, to)."""
    color: str
    entries: List[Tuple[str, str, str, str]] = field(default_factory=list)

    def on_move(self, time_ms: int, piece_code: str,
                from_row: int, from_col: int,
                to_row: int, to_col: int) -> None:
        wall_time = datetime.now().strftime("%H:%M:%S")
        self.entries.append((
            wall_time,
            piece_code[1],
            cell_to_notation(from_row, from_col),
            cell_to_notation(to_row, to_col),
        ))
