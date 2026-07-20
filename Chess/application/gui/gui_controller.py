import cv2
from application.bridge.game_session import GameSession


class GUIController:
    def __init__(self, renderer, session: GameSession):
        self.renderer = renderer
        self.session  = session
        self.selected = None  # (row, col) of currently selected cell

    def get_mouse_callback(self):
        def on_mouse(event, x, y, flags, param):
            if event != cv2.EVENT_LBUTTONDOWN:
                return
            row, col = self.renderer.pixel_to_cell(x, y)
            if not self.renderer.in_bounds(row, col):
                return
            if self.selected == (row, col):
                self.session.jump(row, col)
                self.selected = None
            else:
                self.session.click(row, col)
                if self.selected is None:
                    self.selected = (row, col)
                else:
                    self.selected = None
        return on_mouse
