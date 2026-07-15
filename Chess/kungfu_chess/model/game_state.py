"""
Game state for Kungfu Chess.
Tracks clock, blocked sources, airborne history, selection, and game-over flag.

Event scheduling has moved to RealTimeArbiter.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional

from kungfu_chess.model.board import BoardInterface
from kungfu_chess.realtime.motion import AirborneEvent


@dataclass
class GameState:
    board: BoardInterface
    clock: int = 0
    game_over: bool = False
    selected_piece: Optional[Tuple[int, int]] = None

    _blocked_sources:  set                  = field(default_factory=set)
    _airborne_history: List[AirborneEvent]  = field(default_factory=list)
    _cooldowns:        dict                  = field(default_factory=dict)  # (row,col) -> end_time

    # ------------------------------------------------------------------
    # Cooldown tracking
    # ------------------------------------------------------------------

    def set_cooldown(self, row: int, col: int, end_time: int, kind: str = "long_rest") -> None:
        self._cooldowns[(row, col)] = (end_time, kind)

    def clear_cooldown(self, row: int, col: int) -> None:
        self._cooldowns.pop((row, col), None)

    def is_on_cooldown(self, row: int, col: int) -> bool:
        return (row, col) in self._cooldowns and self.clock < self._cooldowns[(row, col)][0]

    # ------------------------------------------------------------------
    # Blocked-source tracking
    # ------------------------------------------------------------------

    def block_source(self, row: int, col: int) -> None:
        self._blocked_sources.add((row, col))

    def unblock_source(self, row: int, col: int) -> None:
        self._blocked_sources.discard((row, col))

    def is_source_blocked(self, row: int, col: int) -> bool:
        return (row, col) in self._blocked_sources

    # ------------------------------------------------------------------
    # Airborne history (written by arbiter, queried for conflict checks)
    # ------------------------------------------------------------------

    def add_airborne(self, airborne_event: AirborneEvent) -> None:
        self._airborne_history.append(airborne_event)

    def get_airborne_at_square(self, row: int, col: int,
                               at_time: Optional[int] = None) -> List[AirborneEvent]:
        events = [e for e in self._airborne_history
                  if e.row == row and e.col == col]
        if at_time is not None:
            events = [e for e in events
                      if e.start_time <= at_time < e.end_time]
        return events

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def select_piece(self, row: int, col: int) -> None:
        self.selected_piece = (row, col)

    def deselect_piece(self) -> None:
        self.selected_piece = None

    def has_selected_piece(self) -> bool:
        return self.selected_piece is not None

    # ------------------------------------------------------------------
    # Game-over
    # ------------------------------------------------------------------

    def end_game(self) -> None:
        self.game_over = True

    def is_game_over(self) -> bool:
        return self.game_over

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def advance_clock(self, time_delta: int) -> None:
        self.clock += time_delta
