"""
Script runner for Kungfu Chess text-test scripts.
Loads a board + command list and executes every command in order.
"""

from typing import List

from kungfu_chess.model.board import TextBoard
from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.input.controller import CommandExecutor
from kungfu_chess.texttests.script_parser import ScriptParser
from kungfu_chess.io.board_parser import load_from_input, validate_board


class ScriptRunner:
    """Runs a sequence of text commands against a game engine."""

    def __init__(self, board_data: List[List[str]]):
        board = TextBoard(board_data)
        self.engine = GameEngine(board)
        self.executor = CommandExecutor(self.engine)

    def run(self, commands: List[str]) -> None:
        for cmd_string in commands:
            command = ScriptParser.parse(cmd_string)
            if command:
                self.executor.execute(command)


def run_from_stdin() -> None:
    """Entry point: read board + commands from stdin and run the script."""
    board_data, commands = load_from_input()
    if board_data is None or not validate_board(board_data):
        return
    runner = ScriptRunner(board_data)
    runner.run(commands)
