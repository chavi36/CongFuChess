"""
Congfu Chess - Main Entry Point

This file contains the input loader and command execution layer.
"""

import sys
import math
from dataclasses import dataclass
from typing import Optional, Tuple

from config import ERROR_MESSAGES, EMPTY_SQUARE
from game import TextBoard, GameEngine


@dataclass
class Command:
    cmd_type: str
    row: Optional[int] = None
    col: Optional[int] = None
    time: Optional[int] = None


class CommandParser:
    @staticmethod
    def parse(cmd_string: str) -> Optional[Command]:
        cmd_string = cmd_string.strip()
        if cmd_string == "print board":
            return Command(cmd_type='print')
        parts = cmd_string.split()
        if not parts:
            return None
        if parts[0] == "jump" and len(parts) == 3:
            try:
                x, y = int(parts[1]), int(parts[2])
                row, col = CommandParser._pixel_to_grid(x, y)
                return Command(cmd_type='jump', row=row, col=col)
            except (ValueError, IndexError):
                return None
        if parts[0] == "click" and len(parts) == 3:
            try:
                x, y = int(parts[1]), int(parts[2])
                row, col = CommandParser._pixel_to_grid(x, y)
                return Command(cmd_type='click', row=row, col=col)
            except (ValueError, IndexError):
                return None
        if parts[0] == "wait" and len(parts) == 2:
            try:
                time = int(parts[1])
                return Command(cmd_type='wait', time=time)
            except (ValueError, IndexError):
                return None
        return None

    @staticmethod
    def _pixel_to_grid(x: int, y: int) -> Tuple[int, int]:
        col = math.ceil(x / 100) - 1
        row = math.ceil(y / 100) - 1
        return row, col


class CommandExecutor:
    def __init__(self, game_engine: GameEngine):
        self.engine = game_engine

    def execute(self, command: Command) -> bool:
        if command.cmd_type == 'print':
            return self._execute_print()
        if self.engine.state.is_game_over():
            return False
        if command.cmd_type == 'jump':
            return self._execute_jump(command.row, command.col)
        if command.cmd_type == 'click':
            return self._execute_click(command.row, command.col)
        if command.cmd_type == 'wait':
            return self._execute_wait(command.time)
        return False

    def _execute_print(self) -> bool:
        if self.engine.state.has_pending_events():
            max_time = max(self.engine.state.peek_next_event_time(), self.engine.state.clock)
            self.engine.process_pending_moves(until_time=max_time)
        else:
            self.engine.process_pending_moves()
        self.engine.board.print_board()
        return True

    def _execute_jump(self, row: int, col: int) -> bool:
        self.engine.process_pending_moves()
        if not self.engine.board.is_in_bounds(row, col):
            return False
        return self.engine.schedule_jump(row, col, self.engine.state.clock)

    def _execute_click(self, row: int, col: int) -> bool:
        self.engine.process_pending_moves()
        if not self.engine.board.is_in_bounds(row, col):
            return False
        piece = self.engine.board.get_piece(row, col)
        if piece != EMPTY_SQUARE and self.engine.state.is_source_blocked(row, col) and not self.engine.state.has_selected_piece():
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
        success = self.engine.schedule_move(sel_row, sel_col, row, col, self.engine.state.clock)
        self.engine.state.deselect_piece()
        return success

    def _handle_empty_square_click(self, row: int, col: int) -> bool:
        if not self.engine.state.has_selected_piece():
            return False
        sel_row, sel_col = self.engine.state.selected_piece
        success = self.engine.schedule_move(sel_row, sel_col, row, col, self.engine.state.clock)
        self.engine.state.deselect_piece()
        return success

    def _execute_wait(self, wait_time: int) -> bool:
        self.engine.advance_time(wait_time)
        return True


class GameLoader:
    @staticmethod
    def load_from_input() -> tuple:
        lines = [l.strip() for l in sys.stdin if l.strip()]
        if not lines or "Board:" not in lines[0]:
            return None, None
        try:
            b_idx = lines.index("Board:")
            c_idx = lines.index("Commands:")
        except ValueError:
            return None, None
        board_data = [row.split() for row in lines[b_idx + 1:c_idx]]
        commands = lines[c_idx + 1:]
        return board_data, commands

    @staticmethod
    def validate_board(board_data: list) -> bool:
        if not board_data:
            return False
        width = len(board_data[0])
        for row in board_data:
            if len(row) != width:
                print(ERROR_MESSAGES['ROW_WIDTH_MISMATCH'])
                return False
        valid_colors = {'w', 'b'}
        valid_types = {'K', 'Q', 'R', 'B', 'N', 'P'}
        for row in board_data:
            for token in row:
                if token != EMPTY_SQUARE:
                    if len(token) != 2 or token[0] not in valid_colors or token[1] not in valid_types:
                        print(ERROR_MESSAGES['UNKNOWN_TOKEN'])
                        return False
        return True


def main():
    board_data, commands = GameLoader.load_from_input()
    if board_data is None or not GameLoader.validate_board(board_data):
        return
    board = TextBoard(board_data)
    engine = GameEngine(board)
    executor = CommandExecutor(engine)
    for cmd_string in commands:
        command = CommandParser.parse(cmd_string)
        if command:
            executor.execute(command)


if __name__ == "__main__":
    main()
