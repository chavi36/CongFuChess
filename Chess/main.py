# """
# Kungfu Chess — stdin/stdout entry point.

# Input format:
#     Board:
#     <row1>
#     <row2>
#     ...
#     Commands:
#     <cmd1>
#     <cmd2>
#     ...

# Output: the board state after all commands, one row per line.
# """

# import sys
# import math

# # ── constants ────────────────────────────────────────────────────────────────

# EMPTY = '.'
# CELL  = 100          # pixels per cell
# MOVE_TIME_PER_SQUARE = 1000   # ms per square
# JUMP_DURATION        = 1000   # ms airborne

# VALID_COLORS = {'w', 'b'}
# VALID_TYPES  = {'K', 'Q', 'R', 'B', 'N', 'P'}

# PAWN_DIR   = {'w': -1, 'b':  1}
# PAWN_START = {'w':  6, 'b':  1}
# PAWN_PROMO = {'w':  0, 'b':  7}

# # ── helpers ───────────────────────────────────────────────────────────────────

# def pixel_to_grid(px: int, py: int):
#     col = math.ceil(px / CELL) - 1
#     row = math.ceil(py / CELL) - 1
#     return row, col


# def in_bounds(board, row, col):
#     return 0 <= row < len(board) and 0 <= col < len(board[0])


# def get(board, row, col):
#     if not in_bounds(board, row, col):
#         return EMPTY
#     return board[row][col]


# def board_str(board):
#     return '\n'.join(' '.join(row) for row in board)

# # ── move validation ───────────────────────────────────────────────────────────

# def is_valid_move(board, fr, fc, tr, tc):
#     piece = get(board, fr, fc)
#     if piece == EMPTY:
#         return False
#     target = get(board, tr, tc)
#     if target != EMPTY and target[0] == piece[0]:
#         return False          # friendly fire

#     pt = piece[1]
#     dr = tr - fr
#     dc = tc - fc

#     if pt == 'K':
#         return max(abs(dr), abs(dc)) == 1

#     if pt == 'N':
#         return sorted([abs(dr), abs(dc)]) == [1, 2]

#     if pt == 'R':
#         if dr != 0 and dc != 0:
#             return False
#         return _path_clear(board, fr, fc, tr, tc)

#     if pt == 'B':
#         if abs(dr) != abs(dc):
#             return False
#         return _path_clear(board, fr, fc, tr, tc)

#     if pt == 'Q':
#         if dr != 0 and dc != 0 and abs(dr) != abs(dc):
#             return False
#         return _path_clear(board, fr, fc, tr, tc)

#     if pt == 'P':
#         color = piece[0]
#         direction = PAWN_DIR[color]
#         start_row = PAWN_START[color]

#         # diagonal capture
#         if abs(dc) == 1 and dr == direction:
#             return target != EMPTY and target[0] != color

#         # forward one
#         if dc == 0 and dr == direction:
#             return target == EMPTY

#         # forward two from start
#         if dc == 0 and dr == 2 * direction and fr == start_row:
#             mid = get(board, fr + direction, fc)
#             return target == EMPTY and mid == EMPTY

#         return False

#     return False


# def _path_clear(board, fr, fc, tr, tc):
#     sr = (0 if tr == fr else (1 if tr > fr else -1))
#     sc = (0 if tc == fc else (1 if tc > fc else -1))
#     r, c = fr + sr, fc + sc
#     while (r, c) != (tr, tc):
#         if get(board, r, c) != EMPTY:
#             return False
#         r += sr
#         c += sc
#     return True


# def move_distance(fr, fc, tr, tc):
#     return max(abs(tr - fr), abs(tc - fc))

# # ── game logic ────────────────────────────────────────────────────────────────

# def run(board, commands):
#     clock = 0
#     selected = None      # (row, col)
#     blocked  = set()     # source squares that are occupied by in-flight pieces
#     # motions: list of {fr,fc,tr,tc,arrive_at,piece}
#     motions  = []
#     game_over = False

#     def process_arrivals():
#         nonlocal game_over
#         done = []
#         remaining = []
#         for m in motions:
#             if clock >= m['arrive_at']:
#                 done.append(m)
#             else:
#                 remaining.append(m)
#         motions[:] = remaining
#         for m in done:
#             tr, tc, piece = m['tr'], m['tc'], m['piece']
#             # unblock source
#             blocked.discard((m['fr'], m['fc']))
#             if game_over:
#                 continue
#             target = get(board, tr, tc)
#             if target != EMPTY and target[1] == 'K':
#                 game_over = True
#             board[tr][tc] = piece
#             # pawn promotion
#             color = piece[0]
#             if piece[1] == 'P' and tr == PAWN_PROMO[color]:
#                 board[tr][tc] = color + 'Q'

#     for cmd in commands:
#         cmd = cmd.strip()
#         if not cmd:
#             continue

#         parts = cmd.split()

#         if parts[0] == 'wait' and len(parts) == 2:
#             clock += int(parts[1])
#             process_arrivals()
#             continue

#         if parts[0] == 'print' and len(parts) == 2 and parts[1] == 'board':
#             process_arrivals()
#             print(board_str(board), flush=True)
#             continue

#         if parts[0] == 'click' and len(parts) == 3:
#             process_arrivals()
#             if game_over:
#                 continue
#             px, py = int(parts[1]), int(parts[2])
#             row, col = pixel_to_grid(px, py)
#             if not in_bounds(board, row, col):
#                 selected = None
#                 continue
#             piece = get(board, row, col)
#             if selected is None:
#                 if piece != EMPTY and (row, col) not in blocked:
#                     selected = (row, col)
#             else:
#                 sr, sc = selected
#                 if (sr, sc) == (row, col):
#                     selected = None
#                 elif piece != EMPTY and get(board, sr, sc)[0] == piece[0]:
#                     # switch selection to another friendly piece
#                     selected = (row, col)
#                 else:
#                     if is_valid_move(board, sr, sc, row, col):
#                         dist = move_distance(sr, sc, row, col)
#                         arrive = clock + dist * MOVE_TIME_PER_SQUARE
#                         moving_piece = board[sr][sc]
#                         board[sr][sc] = EMPTY
#                         blocked.add((sr, sc))
#                         motions.append({'fr': sr, 'fc': sc,
#                                         'tr': row, 'tc': col,
#                                         'arrive_at': arrive,
#                                         'piece': moving_piece})
#                     selected = None
#             continue

#     # auto-print if no explicit print board
#     process_arrivals()

# # ── I/O ───────────────────────────────────────────────────────────────────────

# def main():
#     sys.stdout.reconfigure(line_buffering=True)

#     lines = [l.rstrip('\n') for l in sys.stdin]

#     # find Board: and Commands: (strip each line to handle leading spaces)
#     stripped = [l.strip() for l in lines]
#     try:
#         b_idx = stripped.index('Board:')
#         c_idx = stripped.index('Commands:')
#     except ValueError:
#         return

#     board_lines = stripped[b_idx + 1:c_idx]
#     commands    = stripped[c_idx + 1:]

#     if not board_lines:
#         return

#     # parse board
#     board = [row.split() for row in board_lines]

#     # validate
#     width = len(board[0])
#     for row in board:
#         if len(row) != width:
#             print('ERROR ROW_WIDTH_MISMATCH', flush=True)
#             return
#     for row in board:
#         for token in row:
#             if token != EMPTY:
#                 if len(token) != 2 or token[0] not in VALID_COLORS or token[1] not in VALID_TYPES:
#                     print('ERROR UNKNOWN_TOKEN', flush=True)
#                     return

#     # run commands — if no 'print board' in commands, print at end
#     had_print = any(c.strip() == 'print board' for c in commands)
#     run(board, commands)
#     if not had_print:
#         print(board_str(board), flush=True)

#     sys.stdout.flush()


# if __name__ == '__main__':
#     main()
"""
Kungfu Chess — stdin/stdout entry point.

Input format:
    Board:
    <row1>
    <row2>
    ...
    Commands:
    <cmd1>
    <cmd2>
    ...

Output: the board state after all commands, one row per line.
"""

import sys
import math

# ── constants ────────────────────────────────────────────────────────────────

EMPTY = '.'
CELL  = 100          # pixels per cell
MOVE_TIME_PER_SQUARE = 1000   # ms per square
JUMP_DURATION        = 1000   # ms airborne

VALID_COLORS = {'w', 'b'}
VALID_TYPES  = {'K', 'Q', 'R', 'B', 'N', 'P'}

PAWN_DIR   = {'w': -1, 'b':  1}
PAWN_START = {'w':  6, 'b':  1}
PAWN_PROMO = {'w':  0, 'b':  7}

# ── helpers ───────────────────────────────────────────────────────────────────

def pixel_to_grid(px: int, py: int):
    col = math.ceil(px / CELL) - 1
    row = math.ceil(py / CELL) - 1
    return row, col


def in_bounds(board, row, col):
    return 0 <= row < len(board) and 0 <= col < len(board[0])


def get(board, row, col):
    if not in_bounds(board, row, col):
        return EMPTY
    return board[row][col]


def board_str(board):
    return '\n'.join(' '.join(row) for row in board)

# ── move validation ───────────────────────────────────────────────────────────

def is_valid_move(board, fr, fc, tr, tc):
    piece = get(board, fr, fc)
    if piece == EMPTY:
        return False
    target = get(board, tr, tc)
    if target != EMPTY and target[0] == piece[0]:
        return False          # friendly fire

    pt = piece[1]
    dr = tr - fr
    dc = tc - fc

    if pt == 'K':
        return max(abs(dr), abs(dc)) == 1

    if pt == 'N':
        return sorted([abs(dr), abs(dc)]) == [1, 2]

    if pt == 'R':
        if dr != 0 and dc != 0:
            return False
        return _path_clear(board, fr, fc, tr, tc)

    if pt == 'B':
        if abs(dr) != abs(dc):
            return False
        return _path_clear(board, fr, fc, tr, tc)

    if pt == 'Q':
        if dr != 0 and dc != 0 and abs(dr) != abs(dc):
            return False
        return _path_clear(board, fr, fc, tr, tc)

    if pt == 'P':
        color = piece[0]
        direction = PAWN_DIR[color]
        start_row = PAWN_START[color]

        # diagonal capture
        if abs(dc) == 1 and dr == direction:
            return target != EMPTY and target[0] != color

        # forward one
        if dc == 0 and dr == direction:
            return target == EMPTY

        # forward two from start
        if dc == 0 and dr == 2 * direction and fr == start_row:
            mid = get(board, fr + direction, fc)
            return target == EMPTY and mid == EMPTY

        return False

    return False


def _path_clear(board, fr, fc, tr, tc):
    sr = (0 if tr == fr else (1 if tr > fr else -1))
    sc = (0 if tc == fc else (1 if tc > fc else -1))
    r, c = fr + sr, fc + sc
    while (r, c) != (tr, tc):
        if get(board, r, c) != EMPTY:
            return False
        r += sr
        c += sc
    return True


def move_distance(fr, fc, tr, tc):
    return max(abs(tr - fr), abs(tc - fc))

# ── game logic ────────────────────────────────────────────────────────────────

def run(board, commands):
    clock = 0
    selected = None      # (row, col)
    blocked  = set()     # source squares that are occupied by in-flight pieces
    # motions: list of {fr,fc,tr,tc,arrive_at,piece}
    motions  = []
    game_over = False

    def process_arrivals():
        nonlocal game_over
        done = []
        remaining = []
        for m in motions:
            if clock >= m['arrive_at']:
                done.append(m)
            else:
                remaining.append(m)
        motions[:] = remaining
        for m in done:
            tr, tc, piece = m['tr'], m['tc'], m['piece']
            # unblock source
            blocked.discard((m['fr'], m['fc']))
            if game_over:
                continue
            target = get(board, tr, tc)
            if target != EMPTY and target[1] == 'K':
                game_over = True
            board[tr][tc] = piece
            # pawn promotion
            color = piece[0]
            if piece[1] == 'P' and tr == PAWN_PROMO[color]:
                board[tr][tc] = color + 'Q'

    for cmd in commands:
        cmd = cmd.strip()
        if not cmd:
            continue

        parts = cmd.split()

        if parts[0] == 'wait' and len(parts) == 2:
            clock += int(parts[1])
            process_arrivals()
            continue

        if parts[0] == 'print' and len(parts) == 2 and parts[1] == 'board':
            process_arrivals()
            print(board_str(board), flush=True)
            continue

        if parts[0] == 'click' and len(parts) == 3:
            process_arrivals()
            if game_over:
                continue
            px, py = int(parts[1]), int(parts[2])
            row, col = pixel_to_grid(px, py)
            if not in_bounds(board, row, col):
                selected = None
                continue
            piece = get(board, row, col)
            if selected is None:
                if piece != EMPTY and (row, col) not in blocked:
                    selected = (row, col)
            else:
                sr, sc = selected
                if (sr, sc) == (row, col):
                    selected = None
                elif piece != EMPTY and get(board, sr, sc)[0] == piece[0]:
                    # switch selection to another friendly piece
                    selected = (row, col)
                else:
                    if is_valid_move(board, sr, sc, row, col):
                        dist = move_distance(sr, sc, row, col)
                        arrive = clock + dist * MOVE_TIME_PER_SQUARE
                        moving_piece = board[sr][sc]
                        board[sr][sc] = EMPTY
                        blocked.add((sr, sc))
                        motions.append({'fr': sr, 'fc': sc,
                                        'tr': row, 'tc': col,
                                        'arrive_at': arrive,
                                        'piece': moving_piece})
                    selected = None
            continue

    # auto-print if no explicit print board
    process_arrivals()

# ── I/O ───────────────────────────────────────────────────────────────────────

def main():
    sys.stdout.reconfigure(line_buffering=True)

    lines = sys.stdin.read().splitlines()

    # find Board: and Commands: (strip each line to handle leading spaces/CR)
    stripped = [l.strip() for l in lines]
    try:
        b_idx = stripped.index('Board:')
        c_idx = stripped.index('Commands:')
    except ValueError:
        return

    board_lines = stripped[b_idx + 1:c_idx]
    commands    = stripped[c_idx + 1:]

    if not board_lines:
        return

    # parse board
    board = [row.split() for row in board_lines]

    # validate
    width = len(board[0])
    for row in board:
        if len(row) != width:
            print('ERROR ROW_WIDTH_MISMATCH', flush=True)
            return
    for row in board:
        for token in row:
            if token != EMPTY:
                if len(token) != 2 or token[0] not in VALID_COLORS or token[1] not in VALID_TYPES:
                    print('ERROR UNKNOWN_TOKEN', flush=True)
                    return

    # run commands — if no 'print board' in commands, print at end
    had_print = any(c.strip() == 'print board' for c in commands)
    run(board, commands)
    if not had_print:
        print(board_str(board), flush=True)

    sys.stdout.flush()


if __name__ == '__main__':
    main()
