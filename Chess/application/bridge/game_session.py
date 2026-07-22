"""
GameSession — bridge between the core engine and the GUI.

Owns the lifecycle of a single game: engine, event bus, observers, and executor.
The GUI only interacts with this class; it never touches the engine directly.
"""

from typing import Optional

from Core.engine.game_engine import GameEngine, RenderSnapshot
from Core.input.controller import CommandExecutor, Command
from Core.io.board_parser import load_board_from_csv
from Core.model.config import PieceColor, EventTopic, CommandType
from Core.model.player import Player
from Core.realtime.event_bus import EventBus
from Core.realtime.move_observer import MoveObserver

_PIECE_COLOR_FOR_ROLE = {
    "white": PieceColor.WHITE.value,
    "black": PieceColor.BLACK.value,
}


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

        self.event_bus      = EventBus()
        self.white_observer = MoveObserver(color=PieceColor.WHITE.value, event_bus=self.event_bus)
        self.black_observer = MoveObserver(color=PieceColor.BLACK.value, event_bus=self.event_bus)

        board = load_board_from_csv(board_csv)
        self.engine = GameEngine(board, players=[white, black], event_bus=self.event_bus)
        self.engine.arbiter.set_observers({
            PieceColor.WHITE.value: self.white_observer,
            PieceColor.BLACK.value: self.black_observer,
        })

        if renderer is not None:
            renderer.set_event_bus(self.event_bus)

        self.executor = CommandExecutor(self.engine)
        self.event_bus.publish(EventTopic.GAME_STARTED, {"clock": 0})

    # ------------------------------------------------------------------
    # GUI-facing API
    # ------------------------------------------------------------------

    def get_render_snapshot(self) -> RenderSnapshot:
        return self.engine.get_render_snapshot(winner=self.winner())

    def send_action(self, action_type: str, row: int = None, col: int = None) -> bool:
        """Satisfies ActionSender protocol — routes to click/jump for local play."""
        if action_type == CommandType.CLICK:
            return self.click(row, col)
        if action_type == CommandType.JUMP:
            return self.jump(row, col)
        return False

    def click_as(self, role: str, row: int, col: int) -> bool:
        """Click enforcing piece ownership — role is 'white' or 'black'."""
        color = _PIECE_COLOR_FOR_ROLE.get(role)
        if color is None:
            return False  # viewer: no write access
        piece = self.engine.board.get_piece(row, col)
        # Allow clicking empty squares only when a piece is already selected
        from Core.model.config import EMPTY_SQUARE
        if piece != EMPTY_SQUARE and piece[0] != color:
            # Trying to select an enemy piece — only allowed as a move target
            if not self.engine.state.has_selected_piece():
                return False
            selected = self.engine.state.selected_piece
            if selected and self.engine.board.get_piece(*selected)[0] != color:
                return False
        return self.click(row, col)

    def jump_as(self, role: str, row: int, col: int) -> bool:
        """Jump enforcing piece ownership — role is 'white' or 'black'."""
        color = _PIECE_COLOR_FOR_ROLE.get(role)
        if color is None:
            return False  # viewer: no write access
        piece = self.engine.board.get_piece(row, col)
        from Core.model.config import EMPTY_SQUARE
        if piece == EMPTY_SQUARE or piece[0] != color:
            return False
        return self.jump(row, col)

    def tick(self, elapsed_ms: int) -> None:
        self.engine.advance_time(elapsed_ms)

    def click(self, row: int, col: int) -> bool:
        return self.executor.execute(Command(cmd_type=CommandType.CLICK, row=row, col=col))

    def jump(self, row: int, col: int) -> bool:
        return self.executor.execute(Command(cmd_type=CommandType.JUMP, row=row, col=col))

    def is_over(self) -> bool:
        return self.engine.state.is_game_over()

    def winner(self) -> Optional[str]:
        if not self.is_over():
            return None
        return self.white.name if self.white.score >= self.black.score else self.black.name
