"""
Configuration and constants for Congfu Chess
All hardcoded values should be here, making it easy to modify and extend
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Tuple, Set


class PieceColor(Enum):
    """Piece colors"""
    WHITE = 'w'
    BLACK = 'b'


class PieceType(Enum):
    """Piece types - easily extensible for custom games"""
    KING = 'K'
    QUEEN = 'Q'
    ROOK = 'R'
    BISHOP = 'B'
    KNIGHT = 'N'
    PAWN = 'P'


# ========== PIECE MOVEMENT RULES ==========
# This configuration makes it trivial to add custom piece types
# or modify movement rules for variant games

PIECE_MOVEMENT_PATTERNS: Dict[str, Dict] = {
    'K': {  # King
        'type': 'jump',
        'max_distance': 1,
        'directions': 'all',
        'blocked_by': 'always',
        'captures': True
    },
    'R': {  # Rook
        'type': 'slide',
        'directions': 'orthogonal',
        'blocked_by': 'always',
        'captures': True
    },
    'B': {  # Bishop
        'type': 'slide',
        'directions': 'diagonal',
        'blocked_by': 'always',
        'captures': True
    },
    'Q': {  # Queen
        'type': 'slide',
        'directions': 'all',
        'blocked_by': 'always',
        'captures': True
    },
    'N': {  # Knight
        'type': 'jump',
        'offsets': [(1, 2), (2, 1), (-1, 2), (-2, 1), 
                    (1, -2), (2, -1), (-1, -2), (-2, -1)],
        'blocked_by': 'never',
        'captures': True
    },
    'P': {  # Pawn (special handling needed)
        'type': 'pawn',
        'move_forward': 1,
        'can_move_two_squares_from_start': True,
        'captures_diagonally': True,
        'promotion_enabled': True,
        'promotion_piece': 'Q'
    }
}

# ========== PAWN SPECIAL CONFIGURATION ==========
# This makes it easy to change pawn behavior for variant games
PAWN_CONFIG = {
    'white': {
        'color': PieceColor.WHITE,
        'direction': -1,  # moves up the board
        'start_row': 6,  # row index in standard 8x8
        'promotion_row': 0
    },
    'black': {
        'color': PieceColor.BLACK,
        'direction': 1,  # moves down the board
        'start_row': 1,
        'promotion_row': 7
    }
}

# ========== TIME CONFIGURATION ==========
# Distances and timing in milliseconds
TIME_CONFIG = {
    'jump_duration': 1000,  # How long a jump lasts
    'move_time_per_square': 1000,  # Moving 1 square = 1000ms
    'check_airborne_capture_instant': True,  # Check capture at click time
    'check_airborne_capture_arrival': True  # Check capture at arrival time
}

# ========== ERROR MESSAGES ==========
ERROR_MESSAGES = {
    'ROW_WIDTH_MISMATCH': 'ERROR ROW_WIDTH_MISMATCH',
    'UNKNOWN_TOKEN': 'ERROR UNKNOWN_TOKEN',
    'INVALID_MOVE': 'ERROR INVALID_MOVE',
    'NO_PIECE_SELECTED': 'ERROR NO_PIECE_SELECTED',
    'INVALID_POSITION': 'ERROR INVALID_POSITION'
}

# ========== BOARD REPRESENTATION ==========
# Future-proofing: these indicate how data flows through the system
# To switch from text to binary representation:
# 1. Create board/binary_representation.py implementing BoardInterface
# 2. Update board/board_factory.py to support both representations
# 3. The rest of the code doesn't need changes due to abstraction!

EMPTY_SQUARE = '.'
BOARD_REPRESENTATION = 'text'  # Can be 'text' or 'binary' in future
