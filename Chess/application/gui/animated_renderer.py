"""
AnimatedRenderer — extends BoardRenderer with per-piece status animations
and visual overlays (selection, cooldown, capture flash, game-over screen).
"""

import time
import numpy as np
import cv2
from application.gui.board_renderer import BoardRenderer
from application.gui.animation_clock import AnimationClock
from application.bridge.game_session import RenderSnapshot

CAPTURE_FLASH_DURATION = 2.0  # seconds

SELECTION_HIGHLIGHT_COLOR_BGR = (0, 180, 0)
CAPTURE_FLASH_COLOR_BGR = (0, 220, 220)
COOLDOWN_BAR_COLOR_BGR = (0, 0, 200)
GAME_OVER_OVERLAY_COLOR_BGR = (80, 80, 80)
GAME_OVER_TEXT_COLOR_BGR = (0, 0, 220)
GAME_OVER_MENU_TEXT_COLOR_BGR = (200, 200, 200)


def _cell_status(snapshot: RenderSnapshot) -> dict:
    status = {}
    for motion in snapshot.active_moves:
        status[(motion.from_row, motion.from_col)] = ("move", motion.start_time)
    for cd in snapshot.cooldowns:
        start_time = cd.end_time - cd.duration
        status[(cd.row, cd.col)] = (cd.kind, start_time)
    return status


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
    def __init__(self, board_path, pieces_dir, window_w, window_h, board_size, event_bus=None):
        super().__init__(board_path, pieces_dir, window_w, window_h, board_size)
        self._anim = AnimationClock(pieces_dir, self.cell_size)
        # (row, col) -> wall time when capture happened
        self._capture_flashes: dict = {}
        self._event_bus = event_bus
        self._animation_flash_until = 0.0
        if self._event_bus is not None:
            self._event_bus.subscribe("capture", self._handle_capture)
            self._event_bus.subscribe("game.ended", self._handle_game_event)
            self._event_bus.subscribe("game.started", self._handle_game_event)

    def set_event_bus(self, event_bus) -> None:
        self._event_bus = event_bus
        if self._event_bus is not None:
            self._event_bus.subscribe("capture", self._handle_capture)
            self._event_bus.subscribe("game.ended", self._handle_game_event)
            self._event_bus.subscribe("game.started", self._handle_game_event)

    def _handle_capture(self, payload) -> None:
        if payload is None:
            return
        self.notify_capture(payload.get("row", 0), payload.get("col", 0))

    def _handle_game_event(self, payload) -> None:
        self._animation_flash_until = time.monotonic() + 0.4

    def notify_capture(self, row: int, col: int) -> None:
        """Call this when a piece is captured at (row, col)."""
        self._capture_flashes[(row, col)] = time.monotonic()

    def render(self, snapshot: RenderSnapshot, selected=None) -> np.ndarray:
        clock    = snapshot.clock
        statuses = _cell_status(snapshot)
        now      = time.monotonic()

        canvas = np.zeros((self.window_h, self.window_w, 3), dtype=np.uint8)
        self._board_img.draw_on_np(canvas, self.offset_x, self.offset_y)

        # ── selection highlight (green) ──────────────────────────────
        if selected is not None:
            r, c = selected
            px = self.offset_x + c * self.cell_size
            py = self.offset_y + r * self.cell_size
            _blend(canvas, px, py, self.cell_size, self.cell_size, SELECTION_HIGHLIGHT_COLOR_BGR, 0.35)

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
            _blend(canvas, px, py, self.cell_size, self.cell_size, CAPTURE_FLASH_COLOR_BGR, alpha)

        # ── moving pieces (interpolated) ─────────────────────────────
        moving_cells = set()
        for motion in snapshot.active_moves:
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
        cd_map = {(cd.row, cd.col): cd for cd in snapshot.cooldowns}
        for r, c, piece in snapshot.board:
            if (r, c) in moving_cells or piece == '.':
                continue
            px = self.offset_x + c * self.cell_size
            py = self.offset_y + r * self.cell_size
            try:
                sprite_code   = self._resolve_code(piece)
                status, start = statuses.get((r, c), ("idle", 0))
                elapsed       = clock - start
                if status in ("long_rest", "short_rest"):
                    cd = cd_map.get((r, c))
                    if cd and cd.duration > 0:
                        entry = self._anim._data.get((sprite_code, status)) \
                             or self._anim._data.get((sprite_code, "idle"))
                        if entry:
                            total_ms = entry["ms_per_frame"] * len(entry["frames"])
                            elapsed  = int(elapsed * total_ms / cd.duration)
                frame = self._anim.get_frame(sprite_code, status, elapsed)
                if frame is None:
                    continue
                frame.draw_on_np(canvas, px, py)
            except FileNotFoundError:
                pass

            # ── cooldown bar ─────────────────────────────────────────
            cd = cd_map.get((r, c))
            if cd and clock < cd.end_time and cd.duration > 0:
                progress = (cd.end_time - clock) / cd.duration
                bar_h    = int(self.cell_size * progress)
                bar_y    = py + self.cell_size - bar_h
                _blend(canvas, px, bar_y, self.cell_size, bar_h, COOLDOWN_BAR_COLOR_BGR, 0.45)

        if now < self._animation_flash_until:
            alpha = 0.15 * (1.0 - (self._animation_flash_until - now) / 0.4)
            _blend(canvas, self.offset_x, self.offset_y,
                   self.board_size, self.board_size, (255, 255, 255), alpha)

        # ── game-over overlay ────────────────────────────────────────
        if snapshot.game_over:
            _blend(canvas, self.offset_x, self.offset_y,
                   self.board_size, self.board_size, GAME_OVER_OVERLAY_COLOR_BGR, 0.6)
            cx = self.offset_x + self.board_size // 2
            cy = self.offset_y + self.board_size // 2
            cv2.putText(canvas, "GAME OVER",
                        (cx - 130, cy - 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.4, GAME_OVER_TEXT_COLOR_BGR, 3)
            if snapshot.winner:
                cv2.putText(canvas, f"{snapshot.winner} wins!",
                            (cx - 100, cy + 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, GAME_OVER_TEXT_COLOR_BGR, 2)
            cv2.putText(canvas, "ESC to quit   any key to restart",
                        (cx - 120, cy + 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, GAME_OVER_MENU_TEXT_COLOR_BGR, 1)

        return canvas
