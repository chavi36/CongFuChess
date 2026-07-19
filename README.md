# KungFu Chess

A real-time chess engine. Both players move simultaneously — pieces travel across the board over time, and a jump makes a piece temporarily airborne and immune to capture.

## Project structure

```
Chess/
├── kungfu_chess/
│   ├── model/
│   │   ├── config.py        # All constants (timing, cooldowns, piece values, cell size, error messages)
│   │   ├── position.py      # Position dataclass (row, col)
│   │   ├── piece.py         # Piece dataclass (color, piece_type)
│   │   ├── player.py        # Player dataclass (name, color, score)
│   │   ├── board.py         # BoardInterface (ABC) + TextBoard implementation
│   │   └── game_state.py    # Clock, blocked sources, airborne history, selection, game-over
│   │
│   ├── rules/
│   │   ├── piece_rules.py   # Per-piece geometry: pawn, knight, sliding (R/B/Q/K)
│   │   └── rule_engine.py   # is_valid_move / get_move_distance — read-only, never mutates board
│   │
│   ├── realtime/
│   │   ├── motion.py        # MoveMotion and AirborneEvent dataclasses
│   │   └── real_time_arbiter.py  # Owns active motions, advances simulated time,
│   │                             # resolves arrivals atomically, detects king capture,
│   │                             # awards score on capture
│   │
│   ├── engine/
│   │   └── game_engine.py   # Coordinator: validates preconditions, delegates to
│   │                        # RuleEngine and RealTimeArbiter. No board mutations.
│   │
│   ├── input/
│   │   ├── board_mapper.py  # pixel_to_grid + get_cell_size (swap for dynamic sizing)
│   │   └── controller.py    # Command dataclass + CommandExecutor (no chess logic here)
│   │
│   ├── io/
│   │   ├── board_parser.py  # load_from_input + validate_board (reads stdin)
│   │   └── board_printer.py # print_board (writes board rows to stdout)
│   │
│   ├── view/
│   │   ├── renderer.py      # Renderer ABC (render / highlight / clear_highlights)
│   │   └── image_view.py    # Graphical stub — implement for pygame/tkinter etc.
│   │
│   ├── gui/
│   │   ├── gui_app.py           # GUI entry point (OpenCV window, game loop, player HUD)
│   │   ├── gui_controller.py    # Mouse input → engine commands
│   │   ├── board_renderer.py    # Static board + piece rendering
│   │   ├── animated_renderer.py # Per-piece state animations (move/jump/rest/idle)
│   │   └── animation_clock.py   # Preloads sprite frames, returns correct frame by clock
│   │
│   ├── anotations/
│   │   ├── pieces1/         # board.csv (initial board layout)
│   │   ├── pieces2/         # Sprite set 2
│   │   ├── pieces3/         # Sprite set 3 (filenames: 1.png, 2.png, ...)
│   │   └── pieces4/         # Sprite set 4 (filenames: tile_R_N.png)
│   │
│   ├── texttests/
│   │   ├── script_parser.py # Maps raw command strings to Command objects
│   │   └── script_runner.py # Thin adapter: parses board + runs commands via engine
│   │
│   └── app.py               # Text-mode entry point — calls script_runner.run_from_stdin()
│
└── tests/
    ├── unit/                # One file per module (68 tests)
    │   ├── test_board.py
    │   ├── test_position.py
    │   ├── test_piece_rules.py
    │   ├── test_rule_engine.py
    │   ├── test_real_time_arbiter.py
    │   ├── test_game_engine.py
    │   ├── test_board_mapper.py
    │   ├── test_controller.py
    │   ├── test_board_parser.py
    │   └── test_board_printer.py
    └── integration/
        ├── test_text_scripts.py   # End-to-end script tests (9 tests)
        └── scripts/               # .kfc fixture files used by the tests
            ├── 01_board_parsing.kfc
            ├── 02_click_to_move.kfc
            ├── 03_rook_moves.kfc
            ├── 04_invalid_moves.kfc
            ├── 05_capture.kfc
            └── 06_game_over.kfc
```

## Layer responsibilities

| Layer | File(s) | Does | Does NOT |
|---|---|---|---|
| **Model** | `board.py`, `game_state.py`, `player.py` | Store state and player info | Validate moves or resolve timing |
| **Rules** | `piece_rules.py`, `rule_engine.py` | Check move geometry | Touch the board |
| **Realtime** | `real_time_arbiter.py` | Track active motions, apply arrivals, detect game-over, award capture score | Know chess rules |
| **Engine** | `game_engine.py` | Coordinate the layers | Contain move rules or mutate the board |
| **Input** | `controller.py` | Route UI commands to engine | Contain chess logic |
| **IO** | `board_parser.py`, `board_printer.py` | Parse / print text | Affect game state |
| **GUI** | `gui_app.py`, `gui_controller.py`, `animated_renderer.py` | Render board, animate pieces, display player HUD | Contain chess logic |

## Run the GUI

Install dependencies:

```bash
pip install opencv-python
```

Run from the `Chess/` directory:

```bash
python -m kungfu_chess.gui.gui_app
```

To switch sprite sets, change `PIECES_SET` at the top of `gui_app.py`:

```python
PIECES_SET = "pieces3"  # pieces1 / pieces2 / pieces3 / pieces4
```

## Run the text engine

Create an input file:

```text
Board:
. . . . . . . .
wR . . . . . . .
. . . . . . . .
Commands:
click 50 150
click 750 150
wait 8000
print board
```

Then run from the `Chess/` directory:

```bash
python -m kungfu_chess.app < input.txt
```

## Supported commands (text mode)

| Command | Effect |
|---|---|
| `print board` | Print the current board state to stdout |
| `click X Y` | Select a piece, move the selected piece, or deselect (click outside board) |
| `jump X Y` | Make the piece at (X, Y) jump — airborne for 1500 ms, immune to capture |
| `wait N` | Advance the simulated clock by N milliseconds |

Coordinates are **pixel-based**: each cell is 100×100 px.
`click 150 250` → col = ceil(150/100)−1 = 1, row = ceil(250/100)−1 = 2.
Cell size is defined in `model/config.py` and read via `input/board_mapper.get_cell_size()`.

## Real-time rules

- A piece that starts moving is **blocked** at its source until it arrives.
- A **jump** makes a piece airborne for 1500 ms. While airborne it is immune to normal capture.
- If an enemy piece moves into a square occupied by an **airborne** piece, the moving piece is destroyed.
- The board is **frozen** after game-over — no further arrivals are applied.
- Clicking outside the board clears the current selection.

## Scoring

Capturing a piece awards points to the capturing player based on standard piece values:

| Piece | Points |
|---|---|
| Pawn | 1 |
| Knight | 3 |
| Bishop | 3 |
| Rook | 5 |
| Queen | 9 |

Scores are displayed live in the GUI above (white) and below (black) the board.
Piece values are configured in `PIECES_VALUES` in `model/config.py`.

## Timing configuration

All timing is in milliseconds and configured in `model/config.py`:

| Setting | Value | Description |
|---|---|---|
| `jump_duration` | 1500 | How long a piece stays airborne |
| `move_time_per_square` | 300 | Travel time per square |
| Move cooldowns | 800–2000 | Per piece type, after arriving |
| Jump cooldowns | 2000–4000 | Per piece type, after landing |

## Run tests

From the `Chess/` directory:

```bash
# Unit tests (68)
python -m unittest discover -s tests/unit

# Integration tests (9)
python -m unittest discover -s tests/integration

# All at once
python -m unittest discover -s tests/unit ; python -m unittest discover -s tests/integration
```

`pytest` is also supported — see `requirements-dev.txt`.
