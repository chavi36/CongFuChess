"""
Image-based view for Kungfu Chess.
Placeholder for a future graphical renderer (e.g. pygame / tkinter).
"""

from kungfu_chess.model.board import BoardInterface
from kungfu_chess.view.renderer import Renderer


class ImageView(Renderer):
    """
    Graphical board renderer — not yet implemented.
    Implement render() / highlight() / clear_highlights() with your
    preferred graphics library.
    """

    def render(self, board: BoardInterface) -> None:
        raise NotImplementedError("ImageView.render() is not implemented yet.")

    def highlight(self, row: int, col: int) -> None:
        raise NotImplementedError("ImageView.highlight() is not implemented yet.")

    def clear_highlights(self) -> None:
        raise NotImplementedError("ImageView.clear_highlights() is not implemented yet.")
