"""
Board printer for Kungfu Chess.
Renders the board to stdout in the standard text format.
"""

from Core.model.board import BoardInterface


def print_board(board: BoardInterface) -> str:
    """Return every row of the board separated by spaces as a string."""
    return "\n".join(
        " ".join(board.get_piece(r, c) for c in range(board.get_width()))
        for r in range(board.get_height())
    )
