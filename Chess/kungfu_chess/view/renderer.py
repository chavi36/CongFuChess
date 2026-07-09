"""
Renderer interface for Kungfu Chess.
Defines the contract that any visual front-end must implement.
"""

from abc import ABC, abstractmethod

from kungfu_chess.model.board import BoardInterface


class Renderer(ABC):
    """Abstract renderer — implement for terminal, pygame, web, etc."""

    @abstractmethod
    def render(self, board: BoardInterface) -> None:
        """Draw the current board state."""
        pass

    @abstractmethod
    def highlight(self, row: int, col: int) -> None:
        """Highlight a specific square (selected piece, valid move, etc.)."""
        pass

    @abstractmethod
    def clear_highlights(self) -> None:
        """Remove all highlights."""
        pass
