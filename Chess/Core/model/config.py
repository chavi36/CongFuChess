"""
Configuration and constants for Kungfu Chess.
"""

from enum import Enum
from typing import Dict


class PieceColor(Enum):
    WHITE = 'w'
    BLACK = 'b'


class PieceType(Enum):
    KING   = 'K'
    QUEEN  = 'Q'
    ROOK   = 'R'
    BISHOP = 'B'
    KNIGHT = 'N'
    PAWN   = 'P'


VALID_COLORS: frozenset = frozenset(c.value for c in PieceColor)
VALID_TYPES:  frozenset = frozenset(t.value for t in PieceType)


PIECE_MOVEMENT_PATTERNS: Dict[str, Dict] = {
    'K': {'type': 'jump', 'max_distance': 1, 'directions': 'all', 'blocked_by': 'always', 'captures': True},
    'R': {'type': 'slide', 'directions': 'orthogonal', 'blocked_by': 'always', 'captures': True},
    'B': {'type': 'slide', 'directions': 'diagonal', 'blocked_by': 'always', 'captures': True},
    'Q': {'type': 'slide', 'directions': 'all', 'blocked_by': 'always', 'captures': True},
    'N': {'type': 'jump', 'offsets': [(1,2),(2,1),(-1,2),(-2,1),(1,-2),(2,-1),(-1,-2),(-2,-1)], 'blocked_by': 'never', 'captures': True},
    'P': {'type': 'pawn', 'move_forward': 1, 'can_move_two_squares_from_start': True, 'captures_diagonally': True, 'promotion_enabled': True, 'promotion_piece': 'Q'},
}

def get_pawn_config(board_height: int) -> dict:
    return {
        'white': {'direction': -1, 'start_row': board_height - 2, 'promotion_row': 0},
        'black': {'direction':  1, 'start_row': 1,                'promotion_row': board_height - 1},
    }

PAWN_CONFIG = get_pawn_config(8)  # default for backward compatibility

TIME_CONFIG = {
    'jump_duration': 3000,           # airborne for 3 s
    'move_time_per_square': 300,     # 300 ms per square travelled
    'check_airborne_capture_instant': True,
    'check_airborne_capture_arrival': True,
}

COOLDOWN_CONFIG = {
    'K': {'move': 3000, 'jump': 6000},
    'Q': {'move': 4000, 'jump': 8000},
    'R': {'move': 3000, 'jump': 6000},
    'B': {'move': 3000, 'jump': 6000},
    'N': {'move': 2000, 'jump': 4000},
    'P': {'move': 1500, 'jump': 4000},
}

# ── Cooldown kind labels ─────────────────────────────────────────────────────
class CooldownKind:
    LONG_REST  = "long_rest"
    SHORT_REST = "short_rest"


# ── Command type labels ───────────────────────────────────────────────────────
class CommandType:
    CLICK = "click"
    JUMP  = "jump"
    WAIT  = "wait"
    PRINT = "print"


# ── Network message type labels ───────────────────────────────────────────────
class MsgType:
    LOGIN        = "login"
    OK           = "ok"
    ERROR        = "error"
    WAITING      = "waiting"
    MATCHED      = "matched"
    SNAPSHOT     = "snapshot"
    CLICK        = "click"
    JUMP         = "jump"
    DISCONNECTED = "disconnected"
    RECONNECTED  = "reconnected"
    FORFEIT      = "forfeit"
    LEADERBOARD  = "leaderboard"
    GAME_OVER    = "game_over"


# ── Event bus topic names ─────────────────────────────────────────────────────
class EventTopic:
    GAME_STARTED  = "game.started"
    GAME_ENDED    = "game.ended"
    MOVE_ARRIVED  = "move.arrived"
    SCORE_UPDATED = "score.updated"
    CAPTURE       = "capture"


ERROR_MESSAGES = {
    'ROW_WIDTH_MISMATCH': 'ERROR ROW_WIDTH_MISMATCH',
    'UNKNOWN_TOKEN':      'ERROR UNKNOWN_TOKEN',
    'INVALID_MOVE':       'ERROR INVALID_MOVE',
    'NO_PIECE_SELECTED':  'ERROR NO_PIECE_SELECTED',
    'INVALID_POSITION':   'ERROR INVALID_POSITION',
}

PIECES_VALUES = {
    "P": 1,
    "N": 3,
    "B": 3,
    "R": 5,
    "Q": 9
}

EMPTY_SQUARE = '.'
BOARD_REPRESENTATION = 'text'

# ========== VIEW CONFIGURATION ==========
CELL_SIZE_PX  = 100   # pixel width/height of one board cell
BOARD_COLS    = 8
BOARD_ROWS    = 8

# ========== GUI LAYOUT ==========
GUI_WINDOW_W  = 1300
GUI_WINDOW_H  = 900
GUI_BOARD_SIZE = 700
GUI_TICK_MS   = 30

# ========== MATCHMAKING ==========
MATCHMAKING_RANGE_TOLERANCE = 1000   # max ELO difference to be matched
MATCHMAKING_STALE_TIMEOUT_S = 60     # seconds before a waiting entry is evicted

# ========== ELO ==========
ELO_DEFAULT  = 1200
ELO_K_FACTOR = 32
ELO_DIVISOR  = 400

# ========== RECONNECTION ==========
RECONNECT_TIMEOUT_S = 60   # seconds a disconnected player has to reconnect

# ========== DATABASE ==========
DB_FILENAME = "kungfu_chess.db"
