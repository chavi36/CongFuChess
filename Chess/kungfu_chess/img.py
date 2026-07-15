import cv2
import numpy as np


class Img:
    def __init__(self):
        self.img = None

    def read(self, path, size=None):
        self.img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if self.img is None:
            raise FileNotFoundError(f"Cannot load image: {path}")
        if size:
            self.img = cv2.resize(self.img, size, interpolation=cv2.INTER_AREA)
        return self

    def draw_on_np(self, canvas, x, y):
        """Draw self onto a raw numpy (H,W,3) BGR canvas at pixel (x, y)."""
        h, w = self.img.shape[:2]
        H, W = canvas.shape[:2]
        x1, y1 = max(x, 0), max(y, 0)
        x2, y2 = min(x + w, W), min(y + h, H)
        sx, sy = x1 - x, y1 - y
        if x2 <= x1 or y2 <= y1:
            return
        src = self.img[sy:sy + (y2 - y1), sx:sx + (x2 - x1)]
        if src.shape[2] == 4:
            alpha = src[..., 3:4] / 255.0
            roi = canvas[y1:y2, x1:x2].astype(np.float32)
            canvas[y1:y2, x1:x2] = ((1 - alpha) * roi + alpha * src[..., :3]).astype(np.uint8)
        else:
            canvas[y1:y2, x1:x2] = src
