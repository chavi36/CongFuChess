"""
AnimationClock — preloads all sprite frames for every (sprite_code, status)
and returns the correct frame image given the current game clock.
"""

import json
import os
from Core.img import Img


class AnimationClock:
    def __init__(self, pieces_dir: str, cell_size: int):
        self._cell_size = cell_size
        self._data: dict = {}   # (sprite_code, status) -> {frames, ms_per_frame, is_loop}
        self._load_all(pieces_dir)

    def _load_all(self, pieces_dir: str) -> None:
        for sprite_code in os.listdir(pieces_dir):
            sprite_path = os.path.join(pieces_dir, sprite_code, "states")
            if not os.path.isdir(sprite_path):
                continue
            for status in os.listdir(sprite_path):
                status_path = os.path.join(sprite_path, status)
                try:
                    self._data[(sprite_code, status)] = self._load_status(status_path)
                except (FileNotFoundError, KeyError, json.JSONDecodeError):
                    pass

    def _load_status(self, status_path: str) -> dict:
        with open(os.path.join(status_path, "config.json")) as f:
            cfg = json.load(f)
        fps       = cfg["graphics"]["frames_per_sec"]
        is_loop   = cfg["graphics"]["is_loop"]
        ms_per_frame = max(1, int(1000 / fps))

        sprites_path = os.path.join(status_path, "sprites")
        frame_files  = sorted(
            (f for f in os.listdir(sprites_path) if f.endswith(".png")),
            key=lambda n: int(os.path.splitext(n)[0].split('_')[-1])
        )
        frames = [
            Img().read(os.path.join(sprites_path, f),
                       size=(self._cell_size, self._cell_size))
            for f in frame_files
        ]
        return {"frames": frames, "ms_per_frame": ms_per_frame, "is_loop": is_loop}

    def get_frame(self, sprite_code: str, status: str, clock: int) -> Img:
        entry = self._data.get((sprite_code, status)) or self._data.get((sprite_code, "idle"))
        if entry is None:
            return None
        frames       = entry["frames"]
        ms_per_frame = entry["ms_per_frame"]
        is_loop      = entry["is_loop"]
        total_frames = len(frames)
        frame_index  = clock // ms_per_frame
        if is_loop:
            frame_index = frame_index % total_frames
        else:
            frame_index = min(frame_index, total_frames - 1)
        return frames[frame_index]
