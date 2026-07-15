"""
AnimatedRenderer — extends BoardRenderer with per-piece status animations.

Drop-in replacement: swap BoardRenderer for AnimatedRenderer in gui_app.py
and pass engine instead of engine.board to render().

To revert: delete this file and animation_clock.py, restore the one-line
changes in gui_app.py.
"""

import numpy as np
from kungfu_chess.gui.board_renderer import BoardRenderer, _to_sprite_code
from kungfu_chess.gui.animation_clock import AnimationClock
from kungfu_chess.engine.game_engine import GameEngine


def _cell_status(engine: GameEngine) -> dict:
    """
    Return {(row, col): (status_string, status_start_ms)} for every occupied cell.
    status_start_ms is the clock time when the piece entered that status,
    so the renderer can compute elapsed time for per-piece animation.
    """
    status = {}
    clock  = engine.state.clock

    # moving pieces — source cell is 'move', started at motion.start_time
    for motion in engine.arbiter._active_moves:
        status[(motion.from_row, motion.from_col)] = ("move", motion.start_time)

    # jumping pieces — 'jump', started at jump.start_time
    for jump in engine.arbiter._active_jumps:
        status[(jump.row, jump.col)] = ("jump", jump.start_time)

    # cooldown pieces — use the kind stored alongside the end_time
    for (row, col), (end_time, kind) in engine.state._cooldowns.items():
        if clock < end_time:
            start_time = end_time - _cooldown_duration(engine, row, col, kind)
            status[(row, col)] = (kind, start_time)

    return status


def _cooldown_duration(engine: GameEngine, row: int, col: int, kind: str) -> int:
    """Look up the cooldown duration for the piece currently at (row, col)."""
    from kungfu_chess.model.config import COOLDOWN_CONFIG
    piece = engine.board.get_piece(row, col)
    if len(piece) < 2:
        return 0
    return COOLDOWN_CONFIG.get(piece[1], {}).get("move" if kind == "long_rest" else "jump", 0)


class AnimatedRenderer(BoardRenderer):
    def __init__(self, board_path, pieces_dir, window_w, window_h, board_size):
        super().__init__(board_path, pieces_dir, window_w, window_h, board_size)
        self._anim = AnimationClock(pieces_dir, self.cell_size)

    def render(self, engine: GameEngine) -> np.ndarray:
        board    = engine.board
        clock    = engine.state.clock
        statuses = _cell_status(engine)

        canvas = np.zeros((self.window_h, self.window_w, 3), dtype=np.uint8)
        self._board_img.draw_on_np(canvas, self.offset_x, self.offset_y)

        # draw moving pieces at interpolated positions
        moving_cells = set()
        for motion in engine.arbiter._active_moves:
            moving_cells.add((motion.from_row, motion.from_col))
            elapsed  = clock - motion.start_time
            duration = motion.arrival_time - motion.start_time
            t        = max(0.0, min(1.0, elapsed / duration)) if duration > 0 else 1.0
            path     = motion.path or [(motion.from_row, motion.from_col), (motion.to_row, motion.to_col)]
            # find which segment of the path we're on
            seg_count = len(path) - 1
            seg_t     = t * seg_count
            seg_i     = min(int(seg_t), seg_count - 1)
            local_t   = seg_t - seg_i
            r0, c0    = path[seg_i]
            r1, c1    = path[seg_i + 1]
            px = self.offset_x + int((c0 + (c1 - c0) * local_t) * self.cell_size)
            py = self.offset_y + int((r0 + (r1 - r0) * local_t) * self.cell_size)
            try:
                sprite_code = self._resolve_code(motion.piece_code)
                frame = self._anim.get_frame(sprite_code, "move", elapsed)
                if frame is not None:
                    frame.draw_on_np(canvas, px, py)
            except FileNotFoundError:
                pass

        for r in range(board.get_height()):
            for c in range(board.get_width()):
                if (r, c) in moving_cells:
                    continue
                piece = board.get_piece(r, c)
                if piece == '.':
                    continue
                try:
                    sprite_code  = self._resolve_code(piece)
                    status, start = statuses.get((r, c), ("idle", 0))
                    elapsed       = clock - start
                    frame         = self._anim.get_frame(sprite_code, status, elapsed)
                    if frame is None:
                        continue
                    px = self.offset_x + c * self.cell_size
                    py = self.offset_y + r * self.cell_size
                    frame.draw_on_np(canvas, px, py)
                except FileNotFoundError:
                    pass

        return canvas
