import unittest
from kungfu_chess.model.position import Position


class TestPosition(unittest.TestCase):
    def test_offset(self):
        p = Position(3, 4)
        self.assertEqual(p.offset(1, -1), Position(4, 3))

    def test_distance_to(self):
        self.assertEqual(Position(0, 0).distance_to(Position(2, 5)), 5)
        self.assertEqual(Position(0, 0).distance_to(Position(3, 3)), 3)

    def test_unpack(self):
        row, col = Position(2, 7)
        self.assertEqual(row, 2)
        self.assertEqual(col, 7)


if __name__ == '__main__':
    unittest.main()
