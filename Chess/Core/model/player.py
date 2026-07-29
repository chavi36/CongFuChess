from dataclasses import dataclass, field
from Core.model.config import PieceColor


@dataclass
class Player:
    name: str
    color: PieceColor
    score: int = field(default=0)

    def add_score(self, points: int = 1) -> None:
        self.score += points
