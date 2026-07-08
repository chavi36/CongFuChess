# CongFuChess

A small chess-like engine with timed movement, airborne jumps, and command-based input.

## What is here

- `main.py` - entry point, command parsing, command execution
- `game.py` - board, game state, move validation, event processing
- `config.py` - all game constants and rules
- `tests.py` - unit tests covering the core logic
- `requirements-dev.txt` - optional dev/test dependencies

## Run the game

Create an input file with this form:

```text
Board:
. . .
. wK .
. . .
Commands:
jump 150 150
wait 1000
print board
```

Then run:

```bash
python main.py < input.txt
```

## Supported commands

- `print board`
- `click X Y`
- `jump X Y`
- `wait N`

Coordinates are converted from pixels to 100×100 grid cells.

## Run tests

```bash
python -m unittest tests.py
```

## Notes

- All game behavior is implemented in Python.
- `config.py` contains the rules, so most changes happen there.
- `tests.py` already includes regression tests for jump and airborne scenarios.

## Why this is enough

This repository now has a single Markdown file for documentation, keeping everything compact and focused.
