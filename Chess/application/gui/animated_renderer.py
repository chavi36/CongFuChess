"""
AnimatedRenderer — extends BoardRenderer with per-piece status animations
and visual overlays (selection, cooldown, capture flash, game-over screen).
"""

import os
import time
from types import SimpleNamespace
import numpy as np
import cv2
from application.gui.board_renderer import BoardRenderer
from application.gui.animation_clock import AnimationClock
from Core.engine.game_engine import RenderSnapshot
from Core.model.config import EMPTY_SQUARE, EventTopic, CooldownKind, BOARD_COLS, BOARD_ROWS

# ── timing constants ──────────────────────────────────────────────────────────
CAPTURE_FLASH_DURATION      = 2.0   # seconds
ANIMATION_FLASH_DURATION    = 0.4   # seconds
ANIMATION_FLASH_ALPHA_SCALE = 0.15

# ── blend alpha constants ─────────────────────────────────────────────────────
SELECTION_ALPHA          = 0.35
CAPTURE_FLASH_ALPHA_MAX  = 0.4
COOLDOWN_BAR_ALPHA       = 0.45
GAME_OVER_OVERLAY_ALPHA  = 0.6

# ── colour constants (BGR) ────────────────────────────────────────────────────
SELECTION_HIGHLIGHT_COLOR_BGR  = (0, 180, 0)
CAPTURE_FLASH_COLOR_BGR        = (0, 220, 220)
COOLDOWN_BAR_COLOR_BGR         = (0, 0, 200)
GAME_OVER_OVERLAY_COLOR_BGR    = (80, 80, 80)
GAME_OVER_TEXT_COLOR_BGR       = (0, 0, 220)
GAME_OVER_MENU_TEXT_COLOR_BGR  = (200, 200, 200)
ANIMATION_FLASH_COLOR_BGR      = (255, 255, 255)

# ── animation status keys ─────────────────────────────────────────────────────
ANIM_STATUS_MOVE = "move"
ANIM_STATUS_IDLE = "idle"


def _coerce_snapshot(snapshot) -> RenderSnapshot:
    if hasattr(snapshot, "clock"):
        return snapshot
    if isinstance(snapshot, dict):
        return SimpleNamespace(
            clock=snapshot.get("clock", 0),
            board=snapshot.get("board", []),
            board_width=snapshot.get("board_width", BOARD_COLS),
            board_height=snapshot.get("board_height", BOARD_ROWS),
            active_moves=[SimpleNamespace(**m) for m in snapshot.get("active_moves", [])],
            cooldowns=[SimpleNamespace(**c) for c in snapshot.get("cooldowns", [])],
            game_over=snapshot.get("game_over", False),
            winner=snapshot.get("winner"),
        )
    return snapshot


def _cell_status(snapshot: RenderSnapshot) -> dict:
    status = {}
    for motion in snapshot.active_moves:
        status[(motion.from_row, motion.from_col)] = (ANIM_STATUS_MOVE, motion.start_time)
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
        self._capture_flashes: dict = {}
        self._event_bus = event_bus
        self._animation_flash_until = 0.0
        if self._event_bus is not None:
            self._subscribe_events()

    def set_event_bus(self, event_bus) -> None:
        self._event_bus = event_bus
        if self._event_bus is not None:
            self._subscribe_events()

    def _subscribe_events(self) -> None:
        self._event_bus.subscribe(EventTopic.CAPTURE, self._handle_capture)
        self._event_bus.subscribe(EventTopic.GAME_ENDED, self._handle_game_event)
        self._event_bus.subscribe(EventTopic.GAME_STARTED, self._handle_game_event)

    def _handle_capture(self, payload) -> None:
        if payload is None:
            return
        self.notify_capture(payload.get("row", 0), payload.get("col", 0))

    def _handle_game_event(self, payload) -> None:
        self._animation_flash_until = time.monotonic() + ANIMATION_FLASH_DURATION

    def notify_capture(self, row: int, col: int) -> None:
        self._capture_flashes[(row, col)] = time.monotonic()

    def render(self, snapshot: RenderSnapshot, selected=None, flipped: bool = False) -> np.ndarray:
        snapshot = _coerce_snapshot(snapshot)
        clock    = snapshot.clock
        statuses = _cell_status(snapshot)
        now      = time.monotonic()

        canvas = np.zeros((self.window_h, self.window_w, 3), dtype=np.uint8)
        self._board_img.draw_on_np(canvas, self.offset_x, self.offset_y)

        def _cell_px(r, c):
            """Convert logical (row, col) to pixel top-left, respecting flip."""
            dr = (BOARD_ROWS - 1 - r) if flipped else r
            dc = (BOARD_COLS - 1 - c) if flipped else c
            return self.offset_x + dc * self.cell_size, self.offset_y + dr * self.cell_size

        # ── selection highlight ──────────────────────────────────────
        if selected is not None:
            r, c = selected
            px, py = _cell_px(r, c)
            _blend(canvas, px, py, self.cell_size, self.cell_size,
                   SELECTION_HIGHLIGHT_COLOR_BGR, SELECTION_ALPHA)

        # ── capture flash ────────────────────────────────────────────
        expired = [k for k, t in self._capture_flashes.items()
                   if now - t > CAPTURE_FLASH_DURATION]
        for k in expired:
            del self._capture_flashes[k]
        for (r, c) in self._capture_flashes:
            px, py = _cell_px(r, c)
            age   = now - self._capture_flashes[(r, c)]
            alpha = CAPTURE_FLASH_ALPHA_MAX * (1.0 - age / CAPTURE_FLASH_DURATION)
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
            # interpolate in logical space then convert to pixel
            log_r = r0 + (r1 - r0) * local_t
            log_c = c0 + (c1 - c0) * local_t
            if flipped:
                log_r = (BOARD_ROWS - 1) - log_r
                log_c = (BOARD_COLS - 1) - log_c
            px = self.offset_x + int(log_c * self.cell_size)
            py = self.offset_y + int(log_r * self.cell_size)
            try:
                sprite_code = self._resolve_code(motion.piece_code)
                frame = self._anim.get_frame(sprite_code, ANIM_STATUS_MOVE, elapsed)
                if frame is not None:
                    frame.draw_on_np(canvas, px, py)
            except FileNotFoundError:
                pass

        # ── stationary pieces ────────────────────────────────────────
        cd_map = {(cd.row, cd.col): cd for cd in snapshot.cooldowns}
        for r, c, piece in snapshot.board:
            if (r, c) in moving_cells or piece == EMPTY_SQUARE:
                continue
            px, py = _cell_px(r, c)
            try:
                sprite_code   = self._resolve_code(piece)
                status, start = statuses.get((r, c), (ANIM_STATUS_IDLE, 0))
                if sprite_code is None:
                    continue
                if not os.path.isdir(os.path.join(self.pieces_dir, sprite_code)):
                    resolved = self._resolve_code(piece)
                    if resolved and os.path.isdir(os.path.join(self.pieces_dir, resolved)):
                        sprite_code = resolved
                elapsed = clock - start
                if status in (CooldownKind.LONG_REST, CooldownKind.SHORT_REST):
                    cd = cd_map.get((r, c))
                    if cd and cd.duration > 0:
                        entry = self._anim._data.get((sprite_code, status)) \
                             or self._anim._data.get((sprite_code, ANIM_STATUS_IDLE))
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
                _blend(canvas, px, bar_y, self.cell_size, bar_h, COOLDOWN_BAR_COLOR_BGR, COOLDOWN_BAR_ALPHA)

        if now < self._animation_flash_until:
            alpha = ANIMATION_FLASH_ALPHA_SCALE * (
                1.0 - (self._animation_flash_until - now) / ANIMATION_FLASH_DURATION
            )
            _blend(canvas, self.offset_x, self.offset_y,
                   self.board_size, self.board_size, ANIMATION_FLASH_COLOR_BGR, alpha)

        # ── game-over overlay ────────────────────────────────────────
        if snapshot.game_over:
            _blend(canvas, self.offset_x, self.offset_y,
                   self.board_size, self.board_size, GAME_OVER_OVERLAY_COLOR_BGR, GAME_OVER_OVERLAY_ALPHA)
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
