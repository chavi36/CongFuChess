"""
Board model for Kungfu Chess.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple

from Core.model.config import EMPTY_SQUARE


class BoardInterface(ABC):
    @abstractmethod
    def get_piece(self, row: int, col: int) -> str:
        pass

    @abstractmethod
    def set_piece(self, row: int, col: int, piece: str) -> None:
        pass

    @abstractmethod
    def is_empty(self, row: int, col: int) -> bool:
        pass

    @abstractmethod
    def is_in_bounds(self, row: int, col: int) -> bool:
        pass

    @abstractmethod
    def get_width(self) -> int:
        pass

    @abstractmethod
    def get_height(self) -> int:
        pass

    @abstractmethod
    def get_all_pieces(self) -> List[Tuple[int, int, str]]:
        pass


class TextBoard(BoardInterface):
    def __init__(self, board_data: List[List[str]]):
        self.board = [row[:] for row in board_data]
        self.height = len(self.board)
        self.width = len(self.board[0]) if self.board else 0

    def get_piece(self, row: int, col: int) -> str:
        if not self.is_in_bounds(row, col):
            return EMPTY_SQUARE
        return self.board[row][col]

    def set_piece(self, row: int, col: int, piece: str) -> None:
        if self.is_in_bounds(row, col):
            self.board[row][col] = piece

    def is_empty(self, row: int, col: int) -> bool:
        return self.get_piece(row, col) == EMPTY_SQUARE

    def is_in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.height and 0 <= col < self.width

    def get_width(self) -> int:
        return self.width

    def get_height(self) -> int:
        return self.height

    def get_all_pieces(self) -> List[Tuple[int, int, str]]:
        pieces = []
        for r in range(self.height):
            for c in range(self.width):
                piece = self.get_piece(r, c)
                if piece != EMPTY_SQUARE:
                    pieces.append((r, c, piece))
        return pieces

    def __repr__(self) -> str:
        return f"TextBoard({self.height}x{self.width})"
