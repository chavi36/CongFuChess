"""
AnimatedRenderer — extends BoardRenderer with per-piece status animations
and visual overlays (selection, cooldown, capture flash, game-over screen).
"""

import time
import numpy as np
import cv2
from kungfu_chess.gui.board_renderer import BoardRenderer
from kungfu_chess.gui.animation_clock import AnimationClock
from kungfu_chess.engine.game_engine import GameEngine

CAPTURE_FLASH_DURATION = 2.0  # seconds


def _cell_status(engine: GameEngine) -> dict:
    status = {}
    clock  = engine.state.clock
    for motion in engine.arbiter._active_moves:
        status[(motion.from_row, motion.from_col)] = ("move", motion.start_time)
    for jump in engine.arbiter._active_jumps:
        status[(jump.row, jump.col)] = ("jump", jump.start_time)
    for (row, col), (end_time, kind) in engine.state._cooldowns.items():
        if clock < end_time:
            start_time = end_time - _cooldown_duration(engine, row, col, kind)
            status[(row, col)] = (kind, start_time)
    return status


def _cooldown_duration(engine: GameEngine, row: int, col: int, kind: str) -> int:
    from kungfu_chess.model.config import COOLDOWN_CONFIG
    piece = engine.board.get_piece(row, col)
    if len(piece) < 2:
        return 0
    return COOLDOWN_CONFIG.get(piece[1], {}).get("move" if kind == "long_rest" else "jump", 0)


def _blend(canvas: np.ndarray, x: int, y: int, w: int, h: int,
           color_bgr: tuple, alpha: float) -> None:
    """Blend a solid rectangle onto canvas with transparency."""
    x1, y1 = max(x, 0), max(y, 0)
    x2, y2 = min(x + w, canvas.shape[1]), min(y + h, canvas.shape[0])
    if x2 <= x1 or y2 <= y1:
        return
    roi = canvas[y1:y2, x1:x2]
    overlay = np.full_like(roi, color_bgr)
    canvas[y1:y2, x1:x2] = cv2.addWeighted(overlay, alpha, roi, 1 - alpha, 0)


class AnimatedRenderer(BoardRenderer):
    def __init__(self, board_path, pieces_dir, window_w, window_h, board_size):
        super().__init__(board_path, pieces_dir, window_w, window_h, board_size)
        self._anim = AnimationClock(pieces_dir, self.cell_size)
        # (row, col) -> wall time when capture happened
        self._capture_flashes: dict = {}

    def notify_capture(self, row: int, col: int) -> None:
        """Call this when a piece is captured at (row, col)."""
        self._capture_flashes[(row, col)] = time.monotonic()

    def render(self, engine: GameEngine, selected=None, winner: str = None) -> np.ndarray:
        board    = engine.board
        clock    = engine.state.clock
        statuses = _cell_status(engine)
        now      = time.monotonic()

        canvas = np.zeros((self.window_h, self.window_w, 3), dtype=np.uint8)
        self._board_img.draw_on_np(canvas, self.offset_x, self.offset_y)

        # ── selection highlight (green) ──────────────────────────────
        if selected is not None:
            r, c = selected
            px = self.offset_x + c * self.cell_size
            py = self.offset_y + r * self.cell_size
            _blend(canvas, px, py, self.cell_size, self.cell_size, (0, 180, 0), 0.35)

        # ── capture flash (yellow) ───────────────────────────────────
        expired = [k for k, t in self._capture_flashes.items()
                   if now - t > CAPTURE_FLASH_DURATION]
        for k in expired:
            del self._capture_flashes[k]
        for (r, c) in self._capture_flashes:
            px = self.offset_x + c * self.cell_size
            py = self.offset_y + r * self.cell_size
            age   = now - self._capture_flashes[(r, c)]
            alpha = 0.4 * (1.0 - age / CAPTURE_FLASH_DURATION)
            _blend(canvas, px, py, self.cell_size, self.cell_size, (0, 220, 220), alpha)

        # ── moving pieces (interpolated) ─────────────────────────────
        moving_cells = set()
        for motion in engine.arbiter._active_moves:
            moving_cells.add((motion.from_row, motion.from_col))
            elapsed  = clock - motion.start_time
            duration = motion.arrival_time - motion.start_time
            t        = max(0.0, min(1.0, elapsed / duration)) if duration > 0 else 1.0
            path     = motion.path or [(motion.from_row, motion.from_col), (motion.to_row, motion.to_col)]
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

        # ── stationary pieces ────────────────────────────────────────
        for r in range(board.get_height()):
            for c in range(board.get_width()):
                if (r, c) in moving_cells:
                    continue
                piece = board.get_piece(r, c)
                if piece == '.':
                    continue
                px = self.offset_x + c * self.cell_size
                py = self.offset_y + r * self.cell_size
                try:
                    sprite_code   = self._resolve_code(piece)
                    status, start = statuses.get((r, c), ("idle", 0))
                    elapsed       = clock - start
                    # for cooldown statuses, stretch elapsed so the animation
                    # plays exactly once over the full cooldown duration
                    if status in ("long_rest", "short_rest"):
                        duration = _cooldown_duration(engine, r, c, status)
                        if duration > 0:
                            entry = self._anim._data.get((sprite_code, status)) \
                                 or self._anim._data.get((sprite_code, "idle"))
                            if entry:
                                total_ms = entry["ms_per_frame"] * len(entry["frames"])
                                elapsed  = int(elapsed * total_ms / duration)
                    frame         = self._anim.get_frame(sprite_code, status, elapsed)
                    if frame is None:
                        continue
                    frame.draw_on_np(canvas, px, py)
                except FileNotFoundError:
                    pass

                # ── cooldown overlay (red bar shrinking downward from top) ────
                if (r, c) in engine.state._cooldowns:
                    end_time, kind = engine.state._cooldowns[(r, c)]
                    if clock < end_time:
                        duration = _cooldown_duration(engine, r, c, kind)
                        progress = (end_time - clock) / duration if duration > 0 else 0
                        bar_h    = int(self.cell_size * progress)
                        # anchor at bottom, shrink upward as cooldown expires
                        bar_y = py + self.cell_size - bar_h
                        _blend(canvas, px, bar_y, self.cell_size, bar_h, (0, 0, 200), 0.45)

        # ── game-over overlay ────────────────────────────────────────
        if engine.state.is_game_over():
            _blend(canvas, self.offset_x, self.offset_y,
                   self.board_size, self.board_size, (80, 80, 80), 0.6)
            cx = self.offset_x + self.board_size // 2
            cy = self.offset_y + self.board_size // 2
            cv2.putText(canvas, "GAME OVER",
                        (cx - 130, cy - 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 220), 3)
            if winner:
                cv2.putText(canvas, f"{winner} wins!",
                            (cx - 100, cy + 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 220), 2)
            cv2.putText(canvas, "ESC to quit   any key to restart",
                        (cx - 190, cy + 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

        return canvas
