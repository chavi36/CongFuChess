"""
Game core module for Congfu Chess
Contains board representation, piece helpers, validation, game state, and engine.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from itertools import count
import heapq

from config import EMPTY_SQUARE, TIME_CONFIG, PAWN_CONFIG, PieceType


class BoardInterface(ABC):
    """Abstract board interface for future representations."""

    @abstractmethod
    def get_piece(self, row: int, col: int) -> str:
        pass

    @abstractmethod
    def set_piece(self, row: int, col: int, piece: str) -> None:
        pass

    @abstractmethod
    def is_empty(self, row: int, col: int) -> bool:
        pass

    @abstractmethod
    def is_in_bounds(self, row: int, col: int) -> bool:
        pass

    @abstractmethod
    def get_width(self) -> int:
        pass

    @abstractmethod
    def get_height(self) -> int:
        pass

    @abstractmethod
    def get_all_pieces(self) -> List[Tuple[int, int, str]]:
        pass

    @abstractmethod
    def print_board(self) -> None:
        pass


class TextBoard(BoardInterface):
    """Text-based board representation."""

    def __init__(self, board_data: List[List[str]]):
        self.board = [row[:] for row in board_data]
        self.height = len(self.board)
        self.width = len(self.board[0]) if self.board else 0

    def get_piece(self, row: int, col: int) -> str:
        if not self.is_in_bounds(row, col):
            return EMPTY_SQUARE
        return self.board[row][col]

    def set_piece(self, row: int, col: int, piece: str) -> None:
        if self.is_in_bounds(row, col):
            self.board[row][col] = piece

    def is_empty(self, row: int, col: int) -> bool:
        return self.get_piece(row, col) == EMPTY_SQUARE

    def is_in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.height and 0 <= col < self.width

    def get_width(self) -> int:
        return self.width

    def get_height(self) -> int:
        return self.height

    def get_all_pieces(self) -> List[Tuple[int, int, str]]:
        pieces = []
        for row in range(self.height):
            for col in range(self.width):
                piece = self.get_piece(row, col)
                if piece != EMPTY_SQUARE:
                    pieces.append((row, col, piece))
        return pieces

    def print_board(self) -> None:
        for row in self.board:
            print(" ".join(row))

    def __repr__(self) -> str:
        return f"TextBoard({self.height}x{self.width})"


@dataclass(frozen=True)
class Piece:
    color: str
    piece_type: str

    @classmethod
    def from_code(cls, code: str) -> 'Piece':
        if len(code) != 2:
            raise ValueError(f"Invalid piece code: {code}")
        return cls(color=code[0], piece_type=code[1])

    def to_code(self) -> str:
        return f"{self.color}{self.piece_type}"

    def is_enemy_of(self, other: 'Piece') -> bool:
        return self.color != other.color


@dataclass
class AirborneEvent:
    row: int
    col: int
    start_time: int
    end_time: int
    color: str


@dataclass
class GameState:
    board: BoardInterface
    clock: int = 0
    game_over: bool = False
    selected_piece: Optional[Tuple[int, int]] = None

    _event_counter: object = field(default_factory=count, init=False, repr=False)
    _pending_events: List = field(default_factory=list)
    _blocked_sources: set = field(default_factory=set)
    _airborne_history: List[AirborneEvent] = field(default_factory=list)

    def get_pending_event(self):
        if self._pending_events:
            return heapq.heappop(self._pending_events)
        return None

    def add_pending_event(self, event_time: int, priority: int, event_type: str,
                         event_data: dict) -> None:
        heapq.heappush(self._pending_events,
                      (event_time, priority, next(self._event_counter), event_type, event_data))

    def has_pending_events(self) -> bool:
        return bool(self._pending_events)

    def peek_next_event_time(self) -> int:
        if self._pending_events:
            return self._pending_events[0][0]
        return float('inf')

    def block_source(self, row: int, col: int) -> None:
        self._blocked_sources.add((row, col))

    def unblock_source(self, row: int, col: int) -> None:
        self._blocked_sources.discard((row, col))

    def is_source_blocked(self, row: int, col: int) -> bool:
        return (row, col) in self._blocked_sources

    def add_airborne(self, airborne_event: AirborneEvent) -> None:
        self._airborne_history.append(airborne_event)

    def get_airborne_at_square(self, row: int, col: int,
                              at_time: Optional[int] = None) -> List[AirborneEvent]:
        events = [e for e in self._airborne_history if e.row == row and e.col == col]
        if at_time is not None:
            events = [e for e in events if e.start_time <= at_time < e.end_time]
        return events

    def select_piece(self, row: int, col: int) -> None:
        self.selected_piece = (row, col)

    def deselect_piece(self) -> None:
        self.selected_piece = None

    def has_selected_piece(self) -> bool:
        return self.selected_piece is not None

    def end_game(self) -> None:
        self.game_over = True

    def is_game_over(self) -> bool:
        return self.game_over

    def advance_clock(self, time_delta: int) -> None:
        self.clock += time_delta


class MoveValidator:
    def __init__(self, board: BoardInterface):
        self.board = board

    def is_valid_move(self, from_row: int, from_col: int,
                      to_row: int, to_col: int) -> bool:
        piece_code = self.board.get_piece(from_row, from_col)
        if not piece_code or piece_code == EMPTY_SQUARE:
            return False

        piece_color = piece_code[0]
        piece_type = piece_code[1]

        target = self.board.get_piece(to_row, to_col)
        if target != EMPTY_SQUARE and target[0] == piece_color:
            return False

        if piece_type == 'P':
            return self._is_valid_pawn_move(from_row, from_col, to_row, to_col, piece_color)
        if piece_type == 'N':
            return self._is_valid_knight_move(from_row, from_col, to_row, to_col)
        if piece_type in 'KQRB':
            return self._is_valid_sliding_move(from_row, from_col, to_row, to_col, piece_type)

        return False

    def _is_valid_pawn_move(self, from_row: int, from_col: int,
                            to_row: int, to_col: int, color: str) -> bool:
        config_key = 'white' if color == 'w' else 'black'
        config = PAWN_CONFIG[config_key]
        direction = config['direction']
        start_row = config['start_row']

        dr, dc = to_row - from_row, to_col - from_col
        if dc == 0:
            if dr == direction:
                return self.board.is_empty(to_row, to_col)
            if dr == 2 * direction and from_row == start_row:
                mid_row = from_row + direction
                return (self.board.is_empty(mid_row, from_col) and
                        self.board.is_empty(to_row, to_col))
            return False
        if abs(dc) == 1 and dr == direction:
            return not self.board.is_empty(to_row, to_col)
        return False

    def _is_valid_knight_move(self, from_row: int, from_col: int,
                              to_row: int, to_col: int) -> bool:
        dr = abs(to_row - from_row)
        dc = abs(to_col - from_col)
        return (dr == 1 and dc == 2) or (dr == 2 and dc == 1)

    def _is_valid_sliding_move(self, from_row: int, from_col: int,
                               to_row: int, to_col: int, piece_type: str) -> bool:
        dr = to_row - from_row
        dc = to_col - from_col
        if dr == 0 and dc == 0:
            return False
        if piece_type == 'K':
            return abs(dr) <= 1 and abs(dc) <= 1
        if piece_type == 'R' and dr != 0 and dc != 0:
            return False
        if piece_type == 'B' and abs(dr) != abs(dc):
            return False
        if piece_type == 'Q' and dr != 0 and dc != 0 and abs(dr) != abs(dc):
            return False
        return self._is_path_clear(from_row, from_col, to_row, to_col)

    def _is_path_clear(self, from_row: int, from_col: int,
                      to_row: int, to_col: int) -> bool:
        dr = 0 if from_row == to_row else (1 if to_row > from_row else -1)
        dc = 0 if from_col == to_col else (1 if to_col > from_col else -1)
        curr_row = from_row + dr
        curr_col = from_col + dc
        while (curr_row, curr_col) != (to_row, to_col):
            if not self.board.is_empty(curr_row, curr_col):
                return False
            curr_row += dr
            curr_col += dc
        return True

    def get_move_distance(self, from_row: int, from_col: int,
                          to_row: int, to_col: int) -> int:
        return max(abs(to_row - from_row), abs(to_col - from_col))


class GameEngine:
    def __init__(self, board: BoardInterface):
        self.board = board
        self.state = GameState(board)
        self.move_validator = MoveValidator(board)
        self._validate_board()

    def _validate_board(self) -> None:
        if not self.board.get_width() or not self.board.get_height():
            raise ValueError("Board must have non-zero dimensions")
        for row, col, piece_code in self.board.get_all_pieces():
            if len(piece_code) != 2:
                raise ValueError(f"Invalid piece code at ({row}, {col}): {piece_code}")
            color, piece_type = piece_code[0], piece_code[1]
            if color not in ['w', 'b']:
                raise ValueError(f"Invalid piece color: {color}")
            if piece_type not in ['K', 'Q', 'R', 'B', 'N', 'P']:
                raise ValueError(f"Invalid piece type: {piece_type}")

    def process_pending_moves(self, until_time: Optional[int] = None) -> None:
        limit_time = until_time if until_time is not None else self.state.clock
        while self.state.has_pending_events():
            next_event_time = self.state.peek_next_event_time()
            if next_event_time > limit_time:
                break
            event_time, priority, _, event_type, event_data = self.state.get_pending_event()
            self.state.clock = event_time
            if event_type == 'land':
                self._handle_land_event(event_data)
            elif event_type == 'move':
                self._handle_move_event(event_data, event_time)

    def _handle_land_event(self, event_data: dict) -> None:
        row, col = event_data['from_row'], event_data['from_col']
        self.state.unblock_source(row, col)

    def _handle_move_event(self, event_data: dict, arrival_time: int) -> None:
        from_row = event_data['from_row']
        from_col = event_data['from_col']
        to_row = event_data['to_row']
        to_col = event_data['to_col']
        move_start_time = event_data['start_time']
        self.state.unblock_source(from_row, from_col)
        if self.board.is_empty(from_row, from_col):
            return
        piece_code = self.board.get_piece(from_row, from_col)
        if self._check_airborne_capture(to_row, to_col, piece_code[0], move_start_time, arrival_time):
            return
        target = self.board.get_piece(to_row, to_col)
        if target != EMPTY_SQUARE and target[0] == piece_code[0]:
            return
        if not self.move_validator.is_valid_move(from_row, from_col, to_row, to_col):
            return
        self._execute_move(from_row, from_col, to_row, to_col)

    def _check_airborne_capture(self, to_row: int, to_col: int,
                               moving_color: str, start_time: int,
                               arrival_time: int) -> bool:
        airborne_pieces = self.state.get_airborne_at_square(to_row, to_col)
        for airborne in airborne_pieces:
            if airborne.color == moving_color:
                continue
            if TIME_CONFIG['check_airborne_capture_instant']:
                if airborne.start_time <= start_time < airborne.end_time:
                    return True
            if TIME_CONFIG['check_airborne_capture_arrival']:
                if airborne.start_time <= arrival_time < airborne.end_time:
                    return True
        return False

    def _execute_move(self, from_row: int, from_col: int,
                      to_row: int, to_col: int) -> None:
        target_piece = self.board.get_piece(to_row, to_col)
        piece_code = self.board.get_piece(from_row, from_col)
        piece_color, piece_type = piece_code[0], piece_code[1]
        if piece_type == 'P':
            config_key = 'white' if piece_color == 'w' else 'black'
            config = PAWN_CONFIG[config_key]
            if to_row == config['promotion_row']:
                piece_code = piece_color + PieceType.QUEEN.value
        self.board.set_piece(to_row, to_col, piece_code)
        self.board.set_piece(from_row, from_col, EMPTY_SQUARE)
        if len(target_piece) > 1 and target_piece[1] == 'K':
            self.state.end_game()

    def schedule_move(self, from_row: int, from_col: int,
                      to_row: int, to_col: int, start_time: int) -> bool:
        if not self.board.is_in_bounds(from_row, from_col):
            return False
        if not self.board.is_in_bounds(to_row, to_col):
            return False
        if self.state.is_source_blocked(from_row, from_col):
            return False
        if self.board.is_empty(from_row, from_col):
            return False
        if not self.move_validator.is_valid_move(from_row, from_col, to_row, to_col):
            return False
        distance = self.move_validator.get_move_distance(from_row, from_col, to_row, to_col)
        arrival_time = start_time + distance * TIME_CONFIG['move_time_per_square']
        piece_color = self.board.get_piece(from_row, from_col)[0]
        if self._check_airborne_capture(to_row, to_col, piece_color, start_time, start_time):
            self.board.set_piece(from_row, from_col, EMPTY_SQUARE)
            return False
        event_data = {
            'from_row': from_row,
            'from_col': from_col,
            'to_row': to_row,
            'to_col': to_col,
            'start_time': start_time
        }
        self.state.add_pending_event(arrival_time, 1, 'move', event_data)
        self.state.block_source(from_row, from_col)
        land_data = {'from_row': from_row, 'from_col': from_col}
        self.state.add_pending_event(arrival_time, 2, 'land', land_data)
        return True

    def schedule_jump(self, row: int, col: int, start_time: int) -> bool:
        if not self.board.is_in_bounds(row, col):
            return False
        if self.board.is_empty(row, col):
            return False
        if self.state.is_source_blocked(row, col):
            return False
        piece_color = self.board.get_piece(row, col)[0]
        end_time = start_time + TIME_CONFIG['jump_duration']
        airborne = AirborneEvent(row=row, col=col, start_time=start_time,
                                 end_time=end_time, color=piece_color)
        self.state.add_airborne(airborne)
        self.state.block_source(row, col)
        land_data = {'from_row': row, 'from_col': col}
        self.state.add_pending_event(end_time, 2, 'land', land_data)
        return True

    def advance_time(self, wait_time: int) -> None:
        target_time = self.state.clock + wait_time
        while self.state.has_pending_events():
            if self.state.is_game_over():
                break
            next_event_time = self.state.peek_next_event_time()
            if next_event_time > target_time:
                break
            self.state.clock = next_event_time
            self.process_pending_moves()
        if not self.state.is_game_over():
            self.state.clock = target_time
            self.process_pending_moves()
