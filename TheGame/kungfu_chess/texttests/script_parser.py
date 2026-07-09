"""
Script parser for Kungfu Chess text-test scripts (.kfc files).
Parses lines like "click 150 250", "wait 1000", "jump 50 150",
"print board" into Command objects.
"""

from typing import Optional

from kungfu_chess.input.board_mapper import pixel_to_grid
from kungfu_chess.input.controller import Command


class ScriptParser:
    """Parses a single command string into a Command."""

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
                row, col = pixel_to_grid(int(parts[1]), int(parts[2]))
                return Command(cmd_type='jump', row=row, col=col)
            except (ValueError, IndexError):
                return None

        if parts[0] == "click" and len(parts) == 3:
            try:
                row, col = pixel_to_grid(int(parts[1]), int(parts[2]))
                return Command(cmd_type='click', row=row, col=col)
            except (ValueError, IndexError):
                return None

        if parts[0] == "wait" and len(parts) == 2:
            try:
                return Command(cmd_type='wait', time=int(parts[1]))
            except (ValueError, IndexError):
                return None

        return None
