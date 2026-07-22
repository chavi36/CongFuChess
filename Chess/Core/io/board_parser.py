"""
Board parser for Kungfu Chess.
Reads the text-based input format and validates the board data.
"""

import sys
from typing import Optional, Tuple, List

from Core.model.config import EMPTY_SQUARE, ERROR_MESSAGES


def load_from_input() -> Tuple[Optional[List[List[str]]], Optional[List[str]]]:
    """Read board data and commands from stdin."""
    lines = [l.strip().strip('*') for l in sys.stdin if l.strip().strip('*')]
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


def validate_board(board_data: List[List[str]]) -> bool:
    """Return True if board_data is structurally valid."""
    if not board_data:
        return False
    width = len(board_data[0])
    for row in board_data:
        if len(row) != width:
            print(ERROR_MESSAGES['ROW_WIDTH_MISMATCH'], flush=True)
            return False
    valid_colors = {'w', 'b'}
    valid_types  = {'K', 'Q', 'R', 'B', 'N', 'P'}
    for row in board_data:
        for token in row:
            if token != EMPTY_SQUARE:
                if (len(token) != 2
                        or token[0] not in valid_colors
                        or token[1] not in valid_types):
                    print(ERROR_MESSAGES['UNKNOWN_TOKEN'], flush=True)
                    return False
    return True
