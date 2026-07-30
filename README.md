# KungFu Chess

A real-time multiplayer chess engine. Both players move simultaneously — pieces travel across the board over time, and a jump makes a piece temporarily airborne and immune to capture.

## Project structure

```
Chess/
├── Core/
│   ├── animations/          # Sprite sets (pieces1–pieces4)
│   ├── engine/
│   │   └── game_engine.py   # Coordinator: validates preconditions, delegates to
│   │                        # RuleEngine and RealTimeArbiter. No board mutations.
│   ├── input/
│   │   ├── board_mapper.py  # pixel_to_grid + get_cell_size
│   │   └── controller.py    # Command dataclass + CommandExecutor
│   ├── io/
│   │   ├── board_parser.py  # load_from_input / load_board_from_csv
│   │   └── board_printer.py # print_board
│   ├── model/
│   │   ├── config.py        # All constants (timing, cooldowns, piece values, cell size, error messages)
│   │   ├── clock.py         # FakeClock / RealClock
│   │   ├── board.py         # BoardInterface (ABC) + TextBoard
│   │   ├── game_state.py    # Clock, blocked sources, airborne history, selection, game-over
│   │   ├── piece.py         # Piece dataclass
│   │   ├── player.py        # Player dataclass
│   │   └── position.py      # Position dataclass
│   ├── realtime/
│   │   ├── event_bus.py     # Re-exports shared InMemoryEventBus
│   │   ├── motion.py        # MoveMotion and AirborneEvent dataclasses
│   │   ├── move_observer.py # Per-color observer that reacts to move events
│   │   └── real_time_arbiter.py  # Owns active motions, resolves arrivals,
│   │                             # detects king capture, awards score
│   ├── rules/
│   │   ├── collision_rules.py   # En-route and destination collision resolution
│   │   ├── piece_rules.py       # Per-piece geometry: pawn, knight, sliding
│   │   └── rule_engine.py       # is_valid_move / get_move_distance — read-only
│   ├── texttests/
│   │   ├── script_parser.py # Maps raw command strings to Command objects
│   │   └── script_runner.py # Parses board + runs commands via engine
│   └── app.py               # Text-mode entry point
│
├── application/
│   ├── bridge/
│   │   └── game_session.py  # Wires engine + executor for local/GUI play
│   ├── gui/
│   │   ├── gui_app.py           # Local GUI entry point (OpenCV, game loop, HUD)
│   │   ├── gui_controller.py    # Mouse input → engine commands
│   │   ├── board_renderer.py    # Static board + piece rendering
│   │   ├── animated_renderer.py # Per-piece state animations
│   │   ├── animation_clock.py   # Preloads sprite frames, returns frame by clock
│   │   └── move_log_panel.py    # Move log + leaderboard side panels
│   └── path_utils.py        # Resolves sprite/board image paths
│
├── client/
│   ├── client.py            # Network client + full GUI (login, menu, game)
│   └── menu_state.py        # Menu navigation state machine
│
├── services/
│   ├── allocator/           # Game-node allocation service
│   ├── api_gateway/         # HTTP API gateway
│   ├── auth/                # Authentication + ELO database
│   ├── edge_gateway/        # WebSocket entry point for clients
│   ├── game_node/           # Per-game engine runner
│   ├── game_orchestrator/   # (reserved)
│   ├── matchmaker/          # Pairs waiting players
│   ├── result_writer/       # Persists game results + ELO updates
│   ├── room_manager/        # Private room creation and joining
│   └── spectator_relay/     # Broadcasts game state to spectators
│
├── shared/
│   ├── events/              # InMemoryEventBus, subjects
│   ├── protocol/            # encode / decode + all message types
│   ├── schema/
│   │   ├── messages.py      # Typed message dataclasses (LoginMsg, SnapshotMsg, …)
│   │   └── transport.py     # JSON serialisation helpers
│   ├── logging.py           # Shared logging config
│   └── metrics.py           # Prometheus metrics helpers
│
├── infra/
│   ├── docker-compose.yml   # Full stack: redis, nats, all services
│   ├── Dockerfile.python    # Python service image
│   ├── Dockerfile.gamenode  # Game-node image
│   ├── prometheus.yml       # Prometheus scrape config
│   └── k8s/                 # Kubernetes manifests
│
├── tests/
│   ├── unit/                # One file per module
│   └── integration/
│       ├── test_text_scripts.py
│       └── scripts/         # .kfc fixture files
│
├── run_server.py            # Launch the WebSocket server (edge gateway)
└── run_client.py            # Launch the GUI client
```

## Layer responsibilities

| Layer | File(s) | Does | Does NOT |
|---|---|---|---|
| **Model** | `Core/model/` | Store state and player info | Validate moves or resolve timing |
| **Rules** | `Core/rules/` | Check move geometry, resolve collisions | Touch the board |
| **Realtime** | `Core/realtime/` | Track active motions, apply arrivals, detect game-over, award capture score | Know chess rules |
| **Engine** | `Core/engine/game_engine.py` | Coordinate the layers | Contain move rules or mutate the board |
| **Bridge** | `application/bridge/game_session.py` | Wire engine + executor for a single game session | Contain chess logic |
| **GUI** | `application/gui/`, `client/client.py` | Render board, animate pieces, display HUD, handle login/menu | Contain chess logic |
| **Services** | `services/` | Matchmaking, auth, game hosting, spectating, results | Know chess rules |
| **Shared** | `shared/` | Protocol encoding, event bus, metrics | Affect game state |
| **IO** | `Core/io/` | Parse / print text boards | Affect game state |

## Run the multiplayer server

Install dependencies:

```bash
pip install opencv-python websockets
```

Run from the `Chess/` directory:

```bash
python run_server.py
```

The server starts on `ws://0.0.0.0:5555` and automatically tries ports 5556–5559 if 5555 is busy.

## Run the GUI client

```bash
python run_client.py
```

A login screen appears. Enter your username and password, then choose from the main menu:

| Option | Effect |
|---|---|
| View Top 10 Leaders | Show the ELO leaderboard |
| Get a Match | Enter the matchmaking queue |
| Create a Room | Create a private room (optional password) |
| Join a Room | Join a private room by ID and password |

To switch sprite sets, change `PIECES_SET` at the top of `client/client.py`:

```python
PIECES_SET = "pieces4"  # pieces1 / pieces2 / pieces3 / pieces4
```

## Run the local GUI (no server)

```bash
python -m application.gui.gui_app
```

## Run the text engine

```bash
python -m Core.app < input.txt
```

Input format:

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

## Supported commands (text mode)

| Command | Effect |
|---|---|
| `print board` | Print the current board state to stdout |
| `click X Y` | Select a piece, move the selected piece, or deselect |
| `jump X Y` | Make the piece at (X, Y) jump — airborne for 1500 ms, immune to capture |
| `wait N` | Advance the simulated clock by N milliseconds |

Coordinates are pixel-based: each cell is 100×100 px.

## Real-time rules

- A piece that starts moving is **blocked** at its source until it arrives.
- A **jump** makes a piece airborne for 1500 ms. While airborne it is immune to normal capture.
- If an enemy piece moves into a square occupied by an **airborne** piece, the moving piece is destroyed.
- **En-route collision**: two pieces passing through the same square at the same time both stop at their last legal position before that square.
- **Destination collision**: same color — the later piece doesn't move; enemy color — the later piece captures.
- The board is **frozen** after game-over — no further arrivals are applied.

## Scoring

| Piece | Points |
|---|---|
| Pawn | 1 |
| Knight | 3 |
| Bishop | 3 |
| Rook | 5 |
| Queen | 9 |

Scores are displayed live in the GUI. Piece values are configured in `PIECES_VALUES` in `Core/model/config.py`.

## Timing configuration

All timing is in milliseconds, configured in `Core/model/config.py`:

| Setting | Value | Description |
|---|---|---|
| `jump_duration` | 1500 | How long a piece stays airborne |
| `move_time_per_square` | 300 | Travel time per square |
| Move cooldowns | 800–2000 | Per piece type, after arriving |
| Jump cooldowns | 2000–4000 | Per piece type, after landing |

## Run with Docker Compose (full stack)

```bash
cd Chess/infra
docker-compose up --build
```

Services started: `redis`, `nats`, `auth`, `api-gateway`, `edge-gateway`, `matchmaker`, `allocator`, `room-manager`, `game-node`, `spectator-relay`, `result-writer`, `prometheus`.

## Run tests

From the `Chess/` directory:

```bash
# Unit tests
python -m unittest discover -s tests/unit

# Integration tests
python -m unittest discover -s tests/integration

# All at once
python -m unittest discover -s tests/unit ; python -m unittest discover -s tests/integration
```

`pytest` is also supported — see `requirements-dev.txt`.
