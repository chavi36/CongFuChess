import cv2
from kungfu_chess.input.controller import Command, CommandExecutor


class GUIController:
    def __init__(self, renderer, executor: CommandExecutor):
        self.renderer  = renderer
        self.executor  = executor
        self.selected  = None  # (row, col) of currently selected cell

    def get_mouse_callback(self):
        def on_mouse(event, x, y, flags, param):
            if event != cv2.EVENT_LBUTTONDOWN:
                return
            row, col = self.renderer.pixel_to_cell(x, y)
            if not self.renderer.in_bounds(row, col):
                return
            if self.selected == (row, col):
                self.executor.execute(Command(cmd_type='jump', row=row, col=col))
                self.selected = None
            else:
                self.executor.execute(Command(cmd_type='click', row=row, col=col))
                # track selection independently — don't rely on engine state
                if self.selected is None:
                    self.selected = (row, col)
                else:
                    self.selected = None
        return on_mouse
