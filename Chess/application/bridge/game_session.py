"""
GameSession — bridge between the core engine and the GUI.

Owns the lifecycle of a single game: engine, event bus, observers, and executor.
The GUI only interacts with this class; it never touches the engine directly.
"""

import csv
from dataclasses import dataclass, field
from typing import Optional

from Core.engine.game_engine import GameEngine
from Core.input.controller import CommandExecutor, Command
from Core.model.board import TextBoard
from Core.model.config import PieceColor, COOLDOWN_CONFIG
from Core.model.player import Player
from Core.realtime.event_bus import EventBus
from Core.realtime.move_observer import MoveObserver


@dataclass
class MotionSnapshot:
    from_row: int
    from_col: int
    to_row: int
    to_col: int
    start_time: int
    arrival_time: int
    piece_code: str
    path: list


@dataclass
class CooldownSnapshot:
    row: int
    col: int
    end_time: int
    kind: str
    duration: int


@dataclass
class RenderSnapshot:
    clock: int
    board: list                          # list of (row, col, piece_code)
    board_width: int
    board_height: int
    active_moves: list                   # list of MotionSnapshot
    cooldowns: list                      # list of CooldownSnapshot
    game_over: bool
    winner: Optional[str] = None


def _load_board(path: str) -> TextBoard:
    with open(path, newline="") as f:
        rows = list(csv.reader(f))

    def convert(code):
        if not code:
            return "."
        piece, color = code[0], code[1]
        return ("w" if color == "W" else "b") + piece

    return TextBoard([[convert(cell) for cell in row] for row in rows])


class GameSession:
    """
    Wires the core (engine + executor) together and exposes a minimal
    interface for the GUI to drive the game.
    """

    def __init__(self, board_csv: str, white: Player, black: Player, renderer=None):
        white.score = 0
        black.score = 0

        self.white = white
        self.black = black

        self.event_bus = EventBus()
        self.white_observer = MoveObserver(color="w", event_bus=self.event_bus)
        self.black_observer = MoveObserver(color="b", event_bus=self.event_bus)

        board = _load_board(board_csv)
        self.engine = GameEngine(board, players=[white, black], event_bus=self.event_bus)
        self.engine.arbiter.set_observers({"w": self.white_observer, "b": self.black_observer})

        if renderer is not None:
            self.engine.arbiter.set_renderer(renderer)
            renderer.set_event_bus(self.event_bus)

        self.executor = CommandExecutor(self.engine)
        self.event_bus.publish("game.started", {"clock": 0})

    # ------------------------------------------------------------------
    # GUI-facing API
    # ------------------------------------------------------------------

    def get_render_snapshot(self) -> RenderSnapshot:
        """Return all data the renderer needs — no engine objects leak out."""
        engine = self.engine
        clock  = engine.state.clock

        board_pieces = [
            (r, c, engine.board.get_piece(r, c))
            for r in range(engine.board.get_height())
            for c in range(engine.board.get_width())
        ]

        active_moves = [
            MotionSnapshot(
                from_row=m.from_row, from_col=m.from_col,
                to_row=m.to_row,     to_col=m.to_col,
                start_time=m.start_time, arrival_time=m.arrival_time,
                piece_code=m.piece_code, path=m.path,
            )
            for m in engine.arbiter._active_moves
        ]

        cooldowns = []
        for (row, col), (end_time, kind) in engine.state._cooldowns.items():
            if clock < end_time:
                piece = engine.board.get_piece(row, col)
                duration = COOLDOWN_CONFIG.get(piece[1], {}).get(
                    "move" if kind == "long_rest" else "jump", 0
                ) if len(piece) >= 2 else 0
                cooldowns.append(CooldownSnapshot(row, col, end_time, kind, duration))

        return RenderSnapshot(
            clock=clock,
            board=board_pieces,
            board_width=engine.board.get_width(),
            board_height=engine.board.get_height(),
            active_moves=active_moves,
            cooldowns=cooldowns,
            game_over=engine.state.is_game_over(),
            winner=self.winner(),
        )

    def tick(self, elapsed_ms: int) -> None:
        """Advance the game clock by elapsed_ms milliseconds."""
        self.engine.advance_time(elapsed_ms)

    def click(self, row: int, col: int) -> bool:
        """Handle a board cell click. Returns True if the action was accepted."""
        return self.executor.execute(Command(cmd_type="click", row=row, col=col))

    def jump(self, row: int, col: int) -> bool:
        """Handle a double-click (jump) on a cell."""
        return self.executor.execute(Command(cmd_type="jump", row=row, col=col))

    def is_over(self) -> bool:
        return self.engine.state.is_game_over()

    def winner(self) -> str | None:
        """Return the winning player's name, or None if the game is still running."""
        if not self.is_over():
            return None
        return self.white.name if self.white.score >= self.black.score else self.black.name
