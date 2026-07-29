"""
Script parser for Kungfu Chess text-test scripts (.kfc files).
Parses lines like "click 150 250", "wait 1000", "jump 50 150",
"print board" into Command objects.
"""

from typing import Optional

from Core.input.board_mapper import pixel_to_grid
from Core.input.controller import Command
from Core.model.config import CommandType


def _parse_pixel_command(cmd_type: str, parts: list) -> Optional[Command]:
    if len(parts) != 3:
        return None
    try:
        row, col = pixel_to_grid(int(parts[1]), int(parts[2]))
        return Command(cmd_type=cmd_type, row=row, col=col)
    except (ValueError, IndexError):
        return None


def _parse_wait(parts: list) -> Optional[Command]:
    if len(parts) != 2:
        return None
    try:
        return Command(cmd_type=CommandType.WAIT, time=int(parts[1]))
    except (ValueError, IndexError):
        return None


_COMMAND_HANDLERS = {
    CommandType.CLICK: lambda parts: _parse_pixel_command(CommandType.CLICK, parts),
    CommandType.JUMP:  lambda parts: _parse_pixel_command(CommandType.JUMP, parts),
    CommandType.WAIT:  _parse_wait,
}


class ScriptParser:
    """Parses a single command string into a Command."""

    @staticmethod
    def parse(cmd_string: str) -> Optional[Command]:
        cmd_string = cmd_string.strip()
        if cmd_string == "print board":
            return Command(cmd_type=CommandType.PRINT)

        parts = cmd_string.split()
        if not parts:
            return None

        handler = _COMMAND_HANDLERS.get(parts[0])
        if handler is None:
            return None
        return handler(parts)
