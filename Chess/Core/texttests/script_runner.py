"""
Script runner for Kungfu Chess text-test scripts.
Loads a board + command list and executes every command in order.
"""

from typing import List

from Core.model.board import TextBoard
from Core.engine.game_engine import GameEngine
from Core.input.controller import CommandExecutor, Command
from Core.texttests.script_parser import ScriptParser
from Core.io.board_parser import load_from_input, validate_board
from Core.io.board_printer import print_board


def _text_printer(board) -> None:
    print(print_board(board), flush=True)


class ScriptRunner:
    """Runs a sequence of text commands against a game engine."""

    def __init__(self, board_data: List[List[str]], on_print=_text_printer):
        board = TextBoard(board_data)
        self.engine = GameEngine(board)
        self.executor = CommandExecutor(self.engine, on_print=on_print)

    def run(self, commands: List[str]) -> None:
        had_print = False
        for cmd_string in commands:
            command = ScriptParser.parse(cmd_string)
            if command:
                if command.cmd_type == 'print':
                    had_print = True
                self.executor.execute(command)
        if not had_print:
            self.executor.execute(Command(cmd_type='print'))


def run_from_stdin() -> None:
    """Entry point: read board + commands from stdin and run the script."""
    board_data, commands = load_from_input()
    if board_data is None or not validate_board(board_data):
        return
    runner = ScriptRunner(board_data)
    runner.run(commands)
