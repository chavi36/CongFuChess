"""
Input controller for Kungfu Chess.
Translates parsed commands into engine calls.
"""

from dataclasses import dataclass
from typing import Optional

from Core.engine.game_engine import GameEngine
from Core.model.config import EMPTY_SQUARE, CommandType


@dataclass
class Command:
    cmd_type: str
    row: Optional[int] = None
    col: Optional[int] = None
    time: Optional[int] = None


class CommandExecutor:
    def __init__(self, game_engine: GameEngine, on_print=None):
        self.engine = game_engine
        self._on_print = on_print

    def execute(self, command: Command) -> bool:
        if command.cmd_type == CommandType.PRINT:
            return self._execute_print()
        if self.engine.state.is_game_over():
            return False
        if command.cmd_type == CommandType.JUMP:
            return self._execute_jump(command.row, command.col)
        if command.cmd_type == CommandType.CLICK:
            return self._execute_click(command.row, command.col)
        if command.cmd_type == CommandType.WAIT:
            return self._execute_wait(command.time)
        return False

    def _execute_print(self) -> bool:
        from Core.io.board_printer import print_board
        self.engine.process_pending_moves()
        if self._on_print:
            self._on_print(self.engine.board)
        return True

    def _execute_jump(self, row: int, col: int) -> bool:
        self.engine.process_pending_moves()
        if not self.engine.board.is_in_bounds(row, col):
            return False
        return self.engine.schedule_jump(row, col, self.engine.state.clock)

    def _execute_click(self, row: int, col: int) -> bool:
        self.engine.process_pending_moves()
        if not self.engine.board.is_in_bounds(row, col):
            # Click outside the board always clears the current selection.
            self.engine.state.deselect_piece()
            return False
        piece = self.engine.board.get_piece(row, col)
        if (piece != EMPTY_SQUARE
                and self.engine.state.is_source_blocked(row, col)
                and not self.engine.state.has_selected_piece()):
            return False
        if piece == EMPTY_SQUARE:
            return self._handle_empty_square_click(row, col)
        return self._handle_piece_click(row, col, piece)

    def _handle_piece_click(self, row: int, col: int, piece: str) -> bool:
        if not self.engine.state.has_selected_piece():
            if self.engine.state.is_source_blocked(row, col):
                return False
            self.engine.state.select_piece(row, col)
            return True
        sel_row, sel_col = self.engine.state.selected_piece
        if sel_row == row and sel_col == col:
            self.engine.state.deselect_piece()
            return True
        selected_piece = self.engine.board.get_piece(sel_row, sel_col)
        if selected_piece[0] == piece[0]:
            self.engine.state.select_piece(row, col)
            return True
        success = self.engine.schedule_move(sel_row, sel_col, row, col,
                                            self.engine.state.clock)
        self.engine.state.deselect_piece()
        return success

    def _handle_empty_square_click(self, row: int, col: int) -> bool:
        if not self.engine.state.has_selected_piece():
            return False
        sel_row, sel_col = self.engine.state.selected_piece
        success = self.engine.schedule_move(sel_row, sel_col, row, col,
                                            self.engine.state.clock)
        self.engine.state.deselect_piece()
        return success

    def _execute_wait(self, wait_time: int) -> bool:
        self.engine.advance_time(wait_time)
        return True
