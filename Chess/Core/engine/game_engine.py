"""
Game engine for Kungfu Chess — coordinator only.

Responsibilities
----------------
- Accept move/jump requests from the controller.
- Check preconditions: bounds, source not blocked, source not empty.
- Ask RuleEngine whether the move is geometrically legal.
- Ask RealTimeArbiter whether an airborne conflict cancels the move.
- Hand the approved motion to RealTimeArbiter for tracking.
- Drive time forward on advance_time() by delegating to the arbiter.
- Assemble RenderSnapshot so no layer above needs to touch engine internals.

Does NOT touch the board directly.
Does NOT decide whether a king was captured.
Does NOT decide when pieces arrive.
"""

from dataclasses import dataclass
from typing import Optional, List

from Core.model.board import BoardInterface
from Core.model.game_state import GameState
from Core.realtime.motion import MoveMotion, AirborneEvent
from Core.realtime.real_time_arbiter import RealTimeArbiter
from Core.rules.rule_engine import RuleEngine
from Core.model.config import (
    EMPTY_SQUARE, VALID_COLORS, VALID_TYPES,
    PieceType, TIME_CONFIG, COOLDOWN_CONFIG, CooldownKind,
)


# ── Snapshot data classes (owned by Core, consumed by the bridge/GUI) ─────────

@dataclass
class MotionSnapshot:
    from_row: int
    from_col: int
    to_row: int
    to_col: int
    start_time: int
    arrival_time: int
    piece_code: str
    path: list


@dataclass
class CooldownSnapshot:
    row: int
    col: int
    end_time: int
    kind: str
    duration: int


@dataclass
class RenderSnapshot:
    clock: int
    board: list
    board_width: int
    board_height: int
    active_moves: List[MotionSnapshot]
    cooldowns: List[CooldownSnapshot]
    game_over: bool
    winner: Optional[str] = None


# ── Engine ────────────────────────────────────────────────────────────────────

class GameEngine:

    def __init__(self, board: BoardInterface, players=None, event_bus=None):
        self.board       = board
        self.state       = GameState(board)
        self.rule_engine = RuleEngine(board)
        self.arbiter     = RealTimeArbiter(board, self.state, players=players, event_bus=event_bus)
        self.arbiter.set_rule_engine(self.rule_engine)
        self._validate_board()

    def _validate_board(self) -> None:
        if not self.board.get_width() or not self.board.get_height():
            raise ValueError("Board must have non-zero dimensions")
        for row, col, piece_code in self.board.get_all_pieces():
            if len(piece_code) != 2:
                raise ValueError(f"Invalid piece code at ({row}, {col}): {piece_code}")
            color, piece_type = piece_code[0], piece_code[1]
            if color not in VALID_COLORS:
                raise ValueError(f"Invalid piece color: {color}")
            if piece_type not in VALID_TYPES:
                raise ValueError(f"Invalid piece type: {piece_type}")

    # ------------------------------------------------------------------
    # Snapshot assembly — the only place that reads engine internals
    # ------------------------------------------------------------------

    def get_render_snapshot(self, winner: Optional[str] = None) -> RenderSnapshot:
        """Assemble a pure-data snapshot for the renderer — no engine objects leak out."""
        clock = self.state.clock

        board_pieces = [
            (r, c, self.board.get_piece(r, c))
            for r in range(self.board.get_height())
            for c in range(self.board.get_width())
        ]

        active_moves = [
            MotionSnapshot(
                from_row=m.from_row, from_col=m.from_col,
                to_row=m.to_row,     to_col=m.to_col,
                start_time=m.start_time, arrival_time=m.arrival_time,
                piece_code=m.piece_code, path=m.path,
            )
            for m in self.arbiter._active_moves
        ]

        cooldowns = []
        for (row, col), (end_time, kind) in self.state._cooldowns.items():
            if clock < end_time:
                piece = self.board.get_piece(row, col)
                duration = COOLDOWN_CONFIG.get(piece[1], {}).get(
                    'move' if kind == CooldownKind.LONG_REST else 'jump', 0
                ) if len(piece) >= 2 else 0
                cooldowns.append(CooldownSnapshot(row, col, end_time, kind, duration))

        return RenderSnapshot(
            clock=clock,
            board=board_pieces,
            board_width=self.board.get_width(),
            board_height=self.board.get_height(),
            active_moves=active_moves,
            cooldowns=cooldowns,
            game_over=self.state.is_game_over(),
            winner=winner,
        )

    # ------------------------------------------------------------------
    # Time advancement — delegates entirely to the arbiter
    # ------------------------------------------------------------------

    def advance_time(self, wait_time: int) -> None:
        target_time = self.state.clock + wait_time
        self.arbiter.advance_to(target_time)
        self.state.clock = target_time

    def process_pending_moves(self, until_time: Optional[int] = None) -> None:
        target = until_time if until_time is not None else self.state.clock
        self.arbiter.advance_to(target)

    # ------------------------------------------------------------------
    # Public API — schedule requests
    # ------------------------------------------------------------------

    def schedule_move(self, from_row: int, from_col: int,
                      to_row: int, to_col: int, start_time: int) -> bool:
        if not self.board.is_in_bounds(from_row, from_col):
            return False
        if not self.board.is_in_bounds(to_row, to_col):
            return False
        if self.state.is_source_blocked(from_row, from_col):
            return False
        if self.state.is_on_cooldown(from_row, from_col):
            return False
        if self.board.is_empty(from_row, from_col):
            return False
        if not self.rule_engine.is_valid_move(from_row, from_col, to_row, to_col):
            return False

        distance     = self.rule_engine.get_move_distance(from_row, from_col, to_row, to_col)
        arrival_time = start_time + distance * TIME_CONFIG['move_time_per_square']
        piece_code   = self.board.get_piece(from_row, from_col)
        piece_color  = piece_code[0]
        piece_type   = piece_code[1]

        if self.arbiter.has_airborne_conflict(
                to_row, to_col, piece_color, start_time, arrival_time):
            self.board.set_piece(from_row, from_col, EMPTY_SQUARE)
            return False

        path = self._compute_path(from_row, from_col, to_row, to_col, piece_type)
        motion = MoveMotion(
            from_row=from_row, from_col=from_col,
            to_row=to_row,     to_col=to_col,
            start_time=start_time, arrival_time=arrival_time,
            piece_code=piece_code,
            path=path,
        )
        self.arbiter.register_move(motion)
        self.state.block_source(from_row, from_col)
        return True

    @staticmethod
    def _compute_path(from_row: int, from_col: int,
                      to_row: int, to_col: int, piece_type: str) -> list:
        if piece_type == PieceType.KNIGHT.value:
            return [(from_row, from_col), (to_row, to_col)]
        dr = 0 if from_row == to_row else (1 if to_row > from_row else -1)
        dc = 0 if from_col == to_col else (1 if to_col > from_col else -1)
        path = []
        r, c = from_row, from_col
        while (r, c) != (to_row, to_col):
            path.append((r, c))
            r += dr
            c += dc
        path.append((to_row, to_col))
        return path

    def schedule_jump(self, row: int, col: int, start_time: int) -> bool:
        if not self.board.is_in_bounds(row, col):
            return False
        if self.board.is_empty(row, col):
            return False
        if self.state.is_source_blocked(row, col):
            return False
        if self.state.is_on_cooldown(row, col):
            return False

        piece_color = self.board.get_piece(row, col)[0]
        end_time    = start_time + TIME_CONFIG['jump_duration']
        jump        = AirborneEvent(row=row, col=col,
                                    start_time=start_time, end_time=end_time,
                                    color=piece_color)
        self.arbiter.register_jump(jump)
        self.state.block_source(row, col)
        return True
