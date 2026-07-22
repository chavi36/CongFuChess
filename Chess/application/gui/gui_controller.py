import cv2
from typing import Protocol, Optional
from Core.model.config import CommandType


class ActionSender(Protocol):
    """Interface that any session object passed to GUIController must satisfy."""
    def send_action(self, action_type: str, row: Optional[int] = None, col: Optional[int] = None) -> None: ...


class GUIController:
    def __init__(self, renderer, session: ActionSender, flipped: bool = False):
        self.renderer = renderer
        self.session  = session
        self.selected = None
        self._flipped = flipped

    def get_mouse_callback(self):
        def on_mouse(event, x, y, flags, param):
            if event != cv2.EVENT_LBUTTONDOWN:
                return
            row, col = self.renderer.pixel_to_cell(x, y)
            if self._flipped:
                from Core.model.config import BOARD_ROWS, BOARD_COLS
                row = BOARD_ROWS - 1 - row
                col = BOARD_COLS - 1 - col
            if not self.renderer.in_bounds(row, col):
                return
            if self.selected == (row, col):
                self.session.send_action(CommandType.JUMP, row=row, col=col)
                self.selected = None
            else:
                self.session.send_action(CommandType.CLICK, row=row, col=col)
                self.selected = None if self.selected is not None else (row, col)
        return on_mouse
