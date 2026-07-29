from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Tuple


from Core.model.config import EventTopic


def cell_to_notation(row: int, col: int) -> str:
    """Convert (row, col) to chess notation e.g. (6, 0) -> a2"""
    return chr(ord('a') + col) + str(8 - row)


@dataclass
class MoveObserver:
    """Records every arrived move for one color as (wall_time, piece_type, from, to)."""
    color: str
    entries: List[Tuple[str, str, str, str]] = field(default_factory=list)

    def __init__(self, color: str, event_bus=None):
        self.color = color
        self.entries: List[Tuple[str, str, str, str]] = []
        self._event_bus = event_bus
        if self._event_bus is not None:
            self._event_bus.subscribe(EventTopic.MOVE_ARRIVED, self._handle_event)

    def _handle_event(self, payload) -> None:
        if payload is None:
            return
        if payload.get("color") != self.color:
            return
        self.on_move(payload.get("clock", 0), payload.get("piece", ""),
                     payload["from"][0], payload["from"][1],
                     payload["to"][0], payload["to"][1])

    def on_move(self, time_ms: int, piece_code: str,
                from_row: int, from_col: int,
                to_row: int, to_col: int) -> None:
        wall_time = datetime.now().strftime("%H:%M:%S")
        self.entries.append((
            wall_time,
            piece_code[1] if len(piece_code) > 1 else piece_code,
            cell_to_notation(from_row, from_col),
            cell_to_notation(to_row, to_col),
        ))
