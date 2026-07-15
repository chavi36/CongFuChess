"""
Piece model for Kungfu Chess.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Piece:
    color: str
    piece_type: str
# פה זה בעצם ניתן לשינוי מהיר- האחריות ברשות הקלאס של פיס
    @classmethod
    def from_code(cls, code: str) -> 'Piece':
        if len(code) != 2:
            raise ValueError(f"Invalid piece code: {code}")
        return cls(color=code[0], piece_type=code[1])

    def to_code(self) -> str:
        return f"{self.color}{self.piece_type}"

    def is_enemy_of(self, other: 'Piece') -> bool:
        return self.color != other.color
