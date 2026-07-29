"""
Board mapper for Kungfu Chess.
Translates pixel coordinates to board (row, col) positions.

To support variable cell sizes in the future, only get_cell_size() needs
to change — pixel_to_grid() and all callers stay the same.
"""

import math
from typing import Tuple

from Core.model.config import CELL_SIZE_PX


def get_cell_size() -> int:
    """
    Return the pixel size of one board cell.
    Replace this function when cell size becomes dynamic
    (e.g. based on window size or config file).
    """
    return CELL_SIZE_PX


def pixel_to_grid(x: int, y: int) -> Tuple[int, int]:
    """Convert pixel (x, y) to board (row, col)."""
    cell = get_cell_size()
    col = math.ceil(x / cell) - 1
    row = math.ceil(y / cell) - 1
    return row, col
